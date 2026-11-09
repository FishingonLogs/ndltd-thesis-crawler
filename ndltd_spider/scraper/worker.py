"""ScraperWorker：在獨立 QThread 中以 Playwright 同步 API 驅動爬蟲。

整合 session + search + detail + captcha + storage，透過 Qt signal 與 GUI 通訊。
速率控制、CAPTCHA 暫停、斷點續爬皆在此協調。
"""

import random
import threading
import time
from datetime import datetime, timezone

from PyQt6.QtCore import QThread, pyqtSignal

from ..config import ScraperConfig
from ..models import QF_FIELDS, SearchConfig, ThesisRecord
from ..storage.database import ThesisDB
from ..storage.exporter import TS_FORMAT, export_run
from .captcha import CaptchaUnsolvedError, is_captcha_page
from .detail import (
    DetailNotFoundError,
    build_detail_url,
    extract_thesis_id,
    parse_detail,
)
from .search import build_record_url, submit_search
from .session import BrowserSession

MODE_SEARCH = "search"
MODE_IDS = "ids"

# CAPTCHA 解題最多重試次數（避免解錯/連續驗證碼時無限彈窗）。
MAX_CAPTCHA_RETRIES = 3
# 連續失敗達此數即中止整批（防 r1 序號超出範圍或頁面結構改變時悶頭跑完全錯）。
MAX_CONSECUTIVE_FAILURES = 5


def _now_iso() -> str:
    """目前時間的 ISO 8601 字串（UTC）。"""
    return datetime.now(timezone.utc).isoformat()


def build_run_log(*, timestamp_text: str, mode_label: str, condition_summary: str,
                  done: int, total: int, skipped: int, failed: int,
                  lines: list[str]) -> str:
    """組裝單次執行的純文字紀錄（標頭 + 條件摘要 + 計數 + 逐筆行）。"""
    head = [
        f"NDLTD 爬取紀錄  {timestamp_text}",
        f"模式: {mode_label}  條件: {condition_summary}",
        f"總數: {total}  成功: {done}  跳過: {skipped}  失敗: {failed}",
        "--------",
    ]
    return "\n".join(head + lines) + "\n"


class ScraperWorker(QThread):
    """背景爬蟲執行緒。

    使用方式：先呼叫 start_search() 或 start_from_ids() 設定模式與參數
    （兩者內部會啟動執行緒），執行中可呼叫 stop() 請求停止、
    resume_after_captcha() 在使用者解完驗證碼後繼續。
    """

    # (已完成, 總數, 跳過, 失敗)
    progress_updated = pyqtSignal(int, int, int, int)
    log_message = pyqtSignal(str)
    captcha_detected = pyqtSignal()
    # 注意：QThread 已內建 finished 信號，故自訂完成信號改名 scrape_finished。
    scrape_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode: str | None = None
        self._search_config: SearchConfig | None = None
        self._id_list: list[str] = []
        self._config = ScraperConfig()
        self._stop_event = threading.Event()
        self._resume_event = threading.Event()
        # 進度計數（done/skipped/failed/total）由 _reset 初始化
        self._reset()

    # ---- GUI 端控制介面 ----

    def start_search(self, search_config: SearchConfig, scraper_config: ScraperConfig) -> None:
        self._mode = MODE_SEARCH
        self._search_config = search_config
        self._config = scraper_config
        self._reset()
        self.start()

    def start_from_ids(self, id_list: list[str], scraper_config: ScraperConfig) -> None:
        self._mode = MODE_IDS
        # 去重並保序
        self._id_list = list(dict.fromkeys(id_list))
        self._config = scraper_config
        self._reset()
        self.start()

    def stop(self) -> None:
        """請求停止（會在完成當前一筆後停止）。"""
        self._stop_event.set()
        # 若正卡在 CAPTCHA 等待，一併解除避免卡死
        self._resume_event.set()

    def resume_after_captcha(self) -> None:
        """使用者解完驗證碼後呼叫，讓 worker 繼續。"""
        self._resume_event.set()

    # ---- 執行緒主體 ----

    def run(self) -> None:
        session = None
        db = None
        try:
            db = ThesisDB(self._config.db_path)
            session = BrowserSession(headless=self._config.headless,
                                     timeout_ms=30000).start()
            # 進站可能直接遇到驗證碼閘門（網站使用量大時），先處理再進入流程
            self._ensure_not_captcha(session)
            session.refresh_ccd()  # 解完驗證碼/轉址後補抓 ccd
            if self._mode == MODE_SEARCH:
                self._run_search(session, db)
            elif self._mode == MODE_IDS:
                self._run_ids(session, db)
            else:
                self.error_occurred.emit(f"未知模式：{self._mode}")
                return
            # 正常完成（非中途停止）且開啟自動匯出時，輸出 CSV + 紀錄檔
            if not self._stop_event.is_set() and self._config.auto_export:
                self._auto_export(db)
            self.scrape_finished.emit()
        except Exception as exc:  # 整體性失敗
            self.error_occurred.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if session:
                session.close()
            if db:
                db.close()

    def _run_search(self, session: BrowserSession, db: ThesisDB) -> None:
        total = submit_search(session, self._search_config)
        self._total = total
        self.log_message.emit(f"搜尋結果共 {total} 筆")
        if total == 0:
            self.log_message.emit("搜尋結果為 0 筆，請確認搜尋條件")
            self._emit_progress()
            return

        consecutive = 0
        for r1 in range(1, total + 1):
            if self._stop_event.is_set():
                self.log_message.emit("已停止")
                break
            url = build_record_url(session.ccd, r1)
            consecutive = self._scrape_and_count(session, db, url, None, consecutive)
            self._emit_progress()
            if self._aborted_on_failures(consecutive):
                break
            self._sleep_between()

    def _run_ids(self, session: BrowserSession, db: ThesisDB) -> None:
        self._total = len(self._id_list)
        consecutive = 0
        for thesis_id in self._id_list:
            if self._stop_event.is_set():
                self.log_message.emit("已停止")
                break
            # ID 模式可在請求前就跳過已完成者
            if db.get_status(thesis_id) == "completed":
                self._skipped += 1
                self._run_lines.append(f"[SKIP] {thesis_id}  （已完成）")
                self.log_message.emit(f"跳過已完成：{thesis_id}")
                self._emit_progress()
                continue
            url = build_detail_url(session.ccd, thesis_id)
            consecutive = self._scrape_and_count(session, db, url, thesis_id, consecutive)
            self._emit_progress()
            if self._aborted_on_failures(consecutive):
                break
            self._sleep_between()

    def _scrape_and_count(self, session: BrowserSession, db: ThesisDB, url: str,
                          thesis_id: str | None, consecutive: int) -> int:
        """爬一筆並回傳更新後的連續失敗計數（成功/跳過歸零）。"""
        failed_before = self._failed
        self._scrape_one(session, db, url, thesis_id=thesis_id)
        return consecutive + 1 if self._failed > failed_before else 0

    def _aborted_on_failures(self, consecutive: int) -> bool:
        """連續失敗達上限時記錄並回報應中止。"""
        if consecutive >= MAX_CONSECUTIVE_FAILURES:
            self.log_message.emit(
                f"連續 {MAX_CONSECUTIVE_FAILURES} 筆失敗，中止"
                "（可能結果序號超出範圍、驗證碼未通過或頁面結構改變）"
            )
            return True
        return False

    def _scrape_one(self, session: BrowserSession, db: ThesisDB,
                    url: str, thesis_id: str | None) -> None:
        """導航、處理 CAPTCHA、解析並寫入單筆。thesis_id 為 None 時由頁面解析。"""
        try:
            session.goto(url)
            html = self._content_after_captcha(session, url)

            resolved_id = thesis_id or extract_thesis_id(html)
            if not resolved_id:
                self._failed += 1
                self._run_lines.append(f"[FAIL] {url}  no_thesis_id")
                self.log_message.emit(f"無法取得論文 ID：{url}")
                return

            # 搜尋模式可能直到此刻才知道 ID，再判一次續爬跳過
            if thesis_id is None and db.get_status(resolved_id) == "completed":
                self._skipped += 1
                self._run_lines.append(f"[SKIP] {resolved_id}  （已完成）")
                self.log_message.emit(f"跳過已完成：{resolved_id}")
                return

            record = parse_detail(html, resolved_id)
            record.status = "completed"
            record.scraped_at = _now_iso()
            db.upsert(record)
            self._done += 1
            self._run_lines.append(f"[OK]   {resolved_id}  {record.title_zh[:30]}")
            self.log_message.emit(f"完成：{resolved_id} {record.title_zh[:20]}")
        except DetailNotFoundError:
            self._record_failure(db, thesis_id, "detail_page_not_found")
            self._run_lines.append(f"[FAIL] {thesis_id or url}  detail_page_not_found")
            self.log_message.emit(f"詳細頁不存在：{thesis_id or url}")
        except Exception as exc:
            self._record_failure(db, thesis_id, f"{type(exc).__name__}: {exc}")
            self._run_lines.append(f"[FAIL] {thesis_id or url}  {type(exc).__name__}: {exc}")
            self.log_message.emit(f"失敗：{thesis_id or url}（{exc}）")

    def _content_after_captcha(self, session: BrowserSession, url: str) -> str:
        """取得頁面 HTML；若為 CAPTCHA 則暫停等人工，解完複驗，仍未過則拋錯。"""
        self._ensure_not_captcha(session)
        return session.content()

    def _ensure_not_captcha(self, session: BrowserSession) -> None:
        """反覆暫停等待人工解題直到通過；解錯/連續驗證碼最多重試 MAX_CAPTCHA_RETRIES 次。

        解完後會「重新偵測」確認真的通過（修正：原本解完不複驗，會把未過的驗證頁
        誤交給 parse_detail 而錯標為 detail_not_found）。stop 觸發時直接返回。
        """
        attempts = 0
        while is_captcha_page(session.content(), session.page.url):
            if self._stop_event.is_set():
                return
            if attempts >= MAX_CAPTCHA_RETRIES:
                raise CaptchaUnsolvedError(
                    f"驗證碼連續 {MAX_CAPTCHA_RETRIES} 次未通過"
                )
            self._pause_for_captcha(session)
            attempts += 1

    def _pause_for_captcha(self, session: BrowserSession) -> None:
        """切 headful、通知 GUI、阻塞等待人工解題，解完切回原模式。"""
        self.log_message.emit("偵測到驗證碼，請於瀏覽器視窗完成驗證後按「確定」")
        self._resume_event.clear()
        session.set_headless(False)
        self.captcha_detected.emit()
        self._resume_event.wait()  # 阻塞直到 GUI 呼叫 resume_after_captcha()/stop()
        # 停止中就別再重啟瀏覽器（set_headless 含最長 30s 的 goto），盡快回迴圈結束，
        # 避免關窗時 worker 仍在跑而 QThread 帶 running 狀態被銷毀。
        if self._stop_event.is_set():
            return
        session.set_headless(self._config.headless)

    # ---- 輔助 ----

    def _record_failure(self, db: ThesisDB, thesis_id: str | None, msg: str) -> None:
        """計入失敗數，並對已知 ID 在 DB 標記 failed（供續爬重試）。"""
        self._failed += 1
        if thesis_id:
            db.upsert(ThesisRecord(thesis_id=thesis_id, status="failed",
                                   error_msg=msg, scraped_at=_now_iso()))

    def _sleep_between(self) -> None:
        if self._stop_event.is_set():
            return
        delay = random.uniform(self._config.delay_min, self._config.delay_max)
        time.sleep(delay)

    def _emit_progress(self) -> None:
        self.progress_updated.emit(self._done, self._total, self._skipped, self._failed)

    def _reset(self) -> None:
        self._stop_event.clear()
        self._resume_event.clear()
        self._done = self._skipped = self._failed = self._total = 0
        self._run_lines: list[str] = []

    # ---- 紀錄與匯出 ----

    def _mode_label(self) -> str:
        return "搜尋" if self._mode == MODE_SEARCH else "ID 清單"

    def _condition_summary(self) -> str:
        """組出本次條件摘要字串（供 log 標頭）。"""
        if self._mode == MODE_IDS:
            return f"{len(self._id_list)} 筆 ID"
        c = self._search_config or SearchConfig()
        parts = []

        segs: list[str] = []
        for row in c.active_rows():
            label = QF_FIELDS.get(row.field, "不限欄位")
            if segs:
                segs.append(row.operator)
            segs.append(f"{label}={row.keyword}")
        if segs:
            parts.append("查詢: " + " ".join(segs))

        degrees = [d for d, on in (("碩士", c.degree_master), ("博士", c.degree_doctor)) if on]
        if degrees:
            parts.append("學位=" + ",".join(degrees))
        if c.year_from or c.year_to:
            parts.append(f"學年度={c.year_from or ''}~{c.year_to or ''}")
        return "; ".join(parts) if parts else "（無條件）"

    def _auto_export(self, db: ThesisDB) -> None:
        """正常完成後自動匯出 CSV 與紀錄檔。"""
        now = datetime.now()
        file_ts = now.strftime(TS_FORMAT)  # 檔名格式由 exporter 單一定義
        human_ts = now.strftime("%Y-%m-%d %H:%M:%S")  # log 內文（人類可讀）
        log_text = build_run_log(
            timestamp_text=human_ts, mode_label=self._mode_label(),
            condition_summary=self._condition_summary(),
            done=self._done, total=self._total,
            skipped=self._skipped, failed=self._failed, lines=self._run_lines,
        )
        csv_path, log_path = export_run(db, self._config.output_dir, log_text, file_ts)
        self.log_message.emit(f"已自動匯出至 {csv_path}")
        self.log_message.emit(f"紀錄檔：{log_path}")
