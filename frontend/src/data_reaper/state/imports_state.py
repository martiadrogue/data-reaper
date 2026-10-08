import reflex as rx

from data_reaper import api_client, forms
from data_reaper.state.auth_state import get_session


class ImportsState(rx.State):
    """Every CSV's import, newest first; admins scan and retry."""

    page: dict = {}  # noqa: RUF012 - Reflex state var
    imports: list[dict] = []  # noqa: RUF012 - Reflex state var
    datasets: list[dict] = []  # noqa: RUF012 - Reflex state var
    status_filter: str = forms.ALL
    offset: int = 0
    error: str = ""
    notice: str = ""
    is_scanning: bool = False

    selected: dict[str, str] = {}  # noqa: RUF012 - Reflex state var
    selected_rejections: list[dict] = []  # noqa: RUF012 - Reflex state var
    detail_open: bool = False

    @rx.var
    def status_counts_text(self) -> str:
        counts = self.page.get("status_counts", {})
        return " · ".join(
            f"{counts.get(status, 0)} {status}" for status in forms.IMPORT_STATUSES
        )

    @rx.var
    def has_next(self) -> bool:
        return forms.next_offset(self.page) is not None

    @rx.var
    def has_previous(self) -> bool:
        return forms.previous_offset(self.page) is not None

    @rx.event
    async def load_imports(self):
        auth = await get_session(self)
        if not auth.is_authenticated:
            return rx.redirect("/login")
        try:
            self.page = await api_client.list_imports(
                auth.token, forms.import_params(self.status_filter, self.offset)
            )
            self.datasets = await api_client.list_datasets(auth.token)
        except api_client.ApiError as exc:
            self.error = exc.message
            return None
        self.imports = [forms.with_display_fields(item) for item in self.page["items"]]
        self.error = ""
        return None

    @rx.event
    def set_status_filter(self, status: str):
        self.status_filter = status
        self.offset = 0
        return ImportsState.load_imports

    @rx.event
    def go_next(self):
        self.offset = forms.next_offset(self.page) or self.offset
        return ImportsState.load_imports

    @rx.event
    def go_previous(self):
        self.offset = forms.previous_offset(self.page) or 0
        return ImportsState.load_imports

    @rx.event
    async def scan(self):
        self.is_scanning = True
        yield
        auth = await get_session(self)
        try:
            result = await api_client.scan_imports(auth.token)
        except api_client.ApiError as exc:
            self.error = exc.message
            self.is_scanning = False
            return
        created = len(result["imports_created"])
        self.notice = (
            f"{result['files_found']} CSV files in the folder; "
            f"{created} new queued for import."
        )
        self.is_scanning = False
        yield ImportsState.load_imports

    @rx.event
    async def retry(self, import_id: str):
        auth = await get_session(self)
        try:
            await api_client.retry_import(auth.token, import_id)
        except api_client.ApiError as exc:
            self.error = exc.message
            return None
        self.notice = "Import queued again."
        return ImportsState.load_imports

    @rx.event
    async def open_detail(self, import_id: str):
        auth = await get_session(self)
        try:
            dataset_import = await api_client.get_import(auth.token, import_id)
        except api_client.ApiError as exc:
            self.error = exc.message
            return
        self.selected = forms.import_detail(dataset_import)
        self.selected_rejections = dataset_import["rejections"]
        self.detail_open = True

    @rx.event
    def set_detail_open(self, is_open: bool):
        self.detail_open = is_open
