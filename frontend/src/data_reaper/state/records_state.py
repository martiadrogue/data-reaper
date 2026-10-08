import reflex as rx

from data_reaper import api_client, forms
from data_reaper.state.auth_state import get_session


class RecordsMixin(rx.State, mixin=True):
    """One Dataset's records: search, source filter, and paging.

    A mixin, so `PlacesState` and `EventsState` each get their own vars;
    each says which Dataset it lists and how its rows are shown.
    """

    page: dict = {}  # noqa: RUF012 - Reflex state var
    records: list[dict] = []  # noqa: RUF012 - Reflex state var
    sources: list[str] = [forms.ALL]  # noqa: RUF012 - Reflex state var
    text_filter: str = ""
    source_filter: str = forms.ALL
    offset: int = 0
    error: str = ""

    @rx.var
    def has_next(self) -> bool:
        return forms.next_offset(self.page) is not None

    @rx.var
    def has_previous(self) -> bool:
        return forms.previous_offset(self.page) is not None

    @rx.var
    def range_text(self) -> str:
        if not self.page:
            return ""
        first = self.page["offset"] + 1 if self.page["items"] else 0
        last = self.page["offset"] + len(self.page["items"])
        return f"{first}–{last} of {self.page['total']}"

    async def _list(self, token: str, params: dict) -> dict:
        raise NotImplementedError

    def _dataset_name(self) -> str:
        raise NotImplementedError

    def _to_row(self, record: dict) -> dict:
        return record

    @rx.event
    async def load_records(self):
        auth = await get_session(self)
        if not auth.is_authenticated:
            return rx.redirect("/login")
        params = forms.record_params(self.text_filter, self.source_filter, self.offset)
        try:
            self.page = await self._list(auth.token, params)
            datasets = await api_client.list_datasets(auth.token)
        except api_client.ApiError as exc:
            self.error = exc.message
            return None
        self.records = [self._to_row(record) for record in self.page["items"]]
        self.sources = forms.source_options(datasets, self._dataset_name())
        self.error = ""
        return None

    @rx.event
    def search(self, form_data: dict):
        self.text_filter = form_data.get("text", "")
        self.offset = 0
        return type(self).load_records

    @rx.event
    def set_source(self, source: str):
        self.source_filter = source
        self.offset = 0
        return type(self).load_records

    @rx.event
    def go_next(self):
        self.offset = forms.next_offset(self.page) or self.offset
        return type(self).load_records

    @rx.event
    def go_previous(self):
        self.offset = forms.previous_offset(self.page) or 0
        return type(self).load_records


class PlacesState(RecordsMixin, rx.State):
    """The places (`dataset_places`)."""

    async def _list(self, token: str, params: dict) -> dict:
        return await api_client.list_places(token, params)

    def _dataset_name(self) -> str:
        return "places"

    def _to_row(self, record: dict) -> dict:
        return forms.with_list_texts(record, "categories")


class EventsState(RecordsMixin, rx.State):
    """The events (`dataset_events`)."""

    async def _list(self, token: str, params: dict) -> dict:
        return await api_client.list_events(token, params)

    def _dataset_name(self) -> str:
        return "events"

    def _to_row(self, record: dict) -> dict:
        return forms.with_list_texts(record, "categories", "organizers")
