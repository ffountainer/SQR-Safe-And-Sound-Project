# main file (frontend)
import json
from typing import Any, Dict, List, Optional

import requests
import streamlit as st
import streamlit.components.v1 as components


DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_MAP_CENTER = (55.751244, 37.618423)
DEFAULT_MAP_ZOOM = 10
DEFAULT_STATUS_ORDER = ["free", "in_process", "broken", "unknown"]


def request_json(method: str, url: str, **kwargs) -> Optional[Any]:
    try:
        response = requests.request(method, url, timeout=10, **kwargs)
        response.raise_for_status()
        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return response.text
    except requests.RequestException as error:
        st.error(f"Ошибка запроса к API: {error}")
        return None


def fetch_machines(api_base_url: str) -> List[Dict[str, Any]]:
    data = request_json(
        "GET",
        f"{api_base_url.rstrip('/')}/machines"
    )
    if isinstance(data, list):
        return data
    return []


def submit_report(api_base_url: str, report_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return request_json(
        "POST",
        f"{api_base_url.rstrip('/')}/report",
        headers={"Content-Type": "application/json"},
        data=json.dumps(report_data),
    )


def normalize_status(status_value: Any) -> str:
    if status_value is None:
        return "unknown"
    text = str(status_value).lower()
    if any(keyword in text for keyword in ["free", "available", "свободна", "idle"]):
        return "free"
    if any(keyword in text for keyword in ["process", "busy", "running", "занят", "в процессе"]):
        return "in_process"
    if any(keyword in text for keyword in ["broken", "error", "fault", "сломана", "неисправ"]):
        return "broken"
    return "unknown"


def status_to_label(status_value: Any) -> str:
    normalized = normalize_status(status_value)
    if normalized == "free":
        return "Свободна"
    if normalized == "in_process":
        return "В процессе"
    if normalized == "broken":
        return "Сломана"
    return str(status_value or "Неизвестно")


def status_sort_key(machine: Dict[str, Any]) -> int:
    status = normalize_status(machine.get("status") or machine.get("state") or machine.get("condition"))
    try:
        return DEFAULT_STATUS_ORDER.index(status)
    except ValueError:
        return len(DEFAULT_STATUS_ORDER) - 1


def extract_floor(machine: Dict[str, Any]) -> Optional[int]:
    for key in ["floor", "level", "этаж", "floor_number", "этаж_номер"]:
        if key in machine:
            try:
                return int(machine[key])
            except (TypeError, ValueError):
                continue
    return None


def extract_building(machine: Dict[str, Any]) -> Optional[str]:
    for key in ["building", "corp", "корпус", "block", "house"]:
        if key in machine and machine[key] is not None:
            return str(machine[key]).strip()
    return None


def extract_time_remaining(machine: Dict[str, Any]) -> Optional[str]:
    for key in ["time_remaining", "time_left", "remaining_time", "time_to_end", "remaining", "left", "ends_in"]:
        if key in machine and machine[key] is not None:
            return str(machine[key])
    if machine.get("status") and isinstance(machine.get("status"), str) and "мин" in machine.get("status"):
        return machine.get("status")
    return None


def format_machine_name(machine: Dict[str, Any]) -> str:
    machine_id = machine.get("id") or machine.get("machine_id") or machine.get("name")
    if machine_id is None:
        return "Без номера"
    return str(machine_id)


def filter_and_sort_machines(
    machines: List[Dict[str, Any]],
    selected_building: Optional[str],
    selected_floor: int,
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for machine in machines:
        floor = extract_floor(machine)
        building = extract_building(machine)
        if selected_building and building and selected_building != building:
            continue
        if floor is None or abs(floor - selected_floor) <= 2:
            filtered.append(machine)
    return sorted(filtered, key=lambda machine: (status_sort_key(machine), extract_floor(machine) or 0, format_machine_name(machine)))


def render_report_panel(api_base_url: str, selected_machine_id: Optional[str]) -> None:
    st.subheader("Создать репорт")
    machine_id = selected_machine_id or st.text_input("ID машины для отчета", value="")
    report_text = st.text_area("Текст отчета", height=140, placeholder="Опишите проблему или состояние машины")
    report_type = st.selectbox("Тип отчета", ["maintenance", "incident", "status"], index=0)

    if st.button("Отправить отчет"):
        if not machine_id.strip() or not report_text.strip():
            st.warning("Укажите ID машины и текст отчета.")
        else:
            payload = {
                "machine_id": machine_id.strip(),
                "type": report_type,
                "message": report_text.strip(),
            }
            result = submit_report(api_base_url, payload)
            if result is not None:
                st.success("Отчет отправлен успешно")
                st.json(result)


def render_machine_list(api_base_url: str, building: Optional[str], floor: int) -> Optional[str]:
    machines = fetch_machines(api_base_url)
    if not machines:
        st.info("Нет данных о машинах. Проверьте URL бэкенда и доступность сервиса.")
        return None

    selected_floor_range = list(range(max(1, floor - 2), floor + 3))
    st.subheader(f"Машины на этажах {selected_floor_range[0]}–{selected_floor_range[-1]}")

    filtered_machines = filter_and_sort_machines(machines, building, floor)
    if not filtered_machines:
        st.write("Нет машин на выбранных этажах или корпусах.")
        return None

    selected_machine_id = None
    for machine in filtered_machines:
        machine_id = format_machine_name(machine)
        machine_floor = extract_floor(machine)
        status_label = status_to_label(machine.get("status") or machine.get("state") or machine.get("condition"))
        time_remaining = extract_time_remaining(machine)

        row = st.container()
        cols = row.columns([2, 1, 1, 1, 1])
        cols[0].markdown(f"**#{machine_id}**")
        cols[1].markdown(f"Этаж\n**{machine_floor if machine_floor is not None else '—'}**")
        cols[2].markdown(f"Статус\n**{status_label}**")
        cols[3].markdown(f"Осталось\n**{time_remaining or '—'}**")
        if cols[4].button("Создать репорт", key=f"report_{machine_id}"):
            st.session_state.selected_report_machine = machine_id
            selected_machine_id = machine_id

    if "selected_report_machine" not in st.session_state:
        st.session_state.selected_report_machine = None

    if st.session_state.selected_report_machine:
        st.markdown("---")
        st.info(f"Создать репорт для машины: {st.session_state.selected_report_machine}")
        render_report_panel(api_base_url, st.session_state.selected_report_machine)

    return st.session_state.selected_report_machine


def render_yandex_map(api_key: str, center: tuple[float, float], zoom: int) -> None:
    map_html = f"""
    <div id="map" style="width: 100%; height: 520px"></div>
    <script src="https://api-maps.yandex.ru/2.1/?lang=ru_RU&apikey={api_key}"></script>
    <script>
        ymaps.ready(function () {{
            const map = new ymaps.Map('map', {{
                center: [{center[0]}, {center[1]}],
                zoom: {zoom},
                controls: ['zoomControl', 'fullscreenControl']
            }});
            map.geoObjects.add(new ymaps.Placemark([{center[0]}, {center[1]}], {{
                hintContent: 'Центр карты',
                balloonContent: 'Яндекс.Карта через внешнее API'
            }}));
        }});
    </script>
    """
    components.html(map_html, height=560, scrolling=False)


def main() -> None:
    st.set_page_config(page_title="SQR Safe And Sound", layout="wide")
    st.title("SQR Safe And Sound — фронтенд")
    st.markdown(
        "Введите корпус и этаж в сайдбаре, чтобы увидеть список машин на этажах N-2..N+2 и создать отчет для конкретной машины."
    )

    if "selected_report_machine" not in st.session_state:
        st.session_state.selected_report_machine = None

    with st.sidebar:
        st.header("Настройки")
        api_base_url = st.text_input("Backend API URL", DEFAULT_API_BASE_URL)
        building_number = st.text_input("Номер корпуса (K)", value="1")
        floor_number = st.number_input("Этаж (N)", min_value=1, max_value=100, value=1)
        yandex_api_key = st.text_input("Yandex Maps API ключ", type="password")
        center_text = st.text_input("Центр карты (lat,lon)", f"{DEFAULT_MAP_CENTER[0]},{DEFAULT_MAP_CENTER[1]}")
        zoom = st.slider("Уровень масштабирования карты", 1, 18, DEFAULT_MAP_ZOOM)

    try:
        lat, lon = [float(item.strip()) for item in center_text.split(",", 1)]
    except ValueError:
        lat, lon = DEFAULT_MAP_CENTER
        st.sidebar.error("Неверный формат центра карты. Используйте lat,lon.")

    cols = st.columns([2, 1])
    with cols[0]:
        render_machine_list(api_base_url, building_number.strip(), floor_number)

    with cols[1]:
        st.subheader("Яндекс.Карты")
        if yandex_api_key:
            render_yandex_map(yandex_api_key, (lat, lon), zoom)
        else:
            st.warning("Укажите API ключ Яндекс.Карт в боковой панели для отображения виджета.")
            st.info(
                "Для демонстрации можно использовать сервисный ключ Yandex Maps API или зарегистрировать свой на https://developer.tech.yandex.ru/"
            )


if __name__ == "__main__":
    main()

