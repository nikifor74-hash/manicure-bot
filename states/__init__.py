from aiogram.fsm.state import State, StatesGroup


class AppointmentStates(StatesGroup):
    choosing_date = State()
    choosing_time = State()
    entering_name = State()
    entering_phone = State()


class AddPhoto(StatesGroup):
    choosing_category = State()
    uploading_photo = State()
    entering_caption = State()
    entering_price = State()


class EditPrice(StatesGroup):
    choosing_action = State()
    entering_service = State()
    entering_price = State()
    entering_description = State()


class SetSchedule(StatesGroup):
    choosing_day = State()
    entering_start = State()
    entering_end = State()
    confirming = State()


class Broadcast(StatesGroup):
    entering_message = State()
    confirming = State()
