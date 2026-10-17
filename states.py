from aiogram.fsm.state import State, StatesGroup

class Creation(StatesGroup):
    service = State()
    topic = State()
    subject = State()
    language = State()
    design = State()
    slide_count = State()
    option = State()
    format = State()
    author = State()   # ✅ YANGI: muallif ismi (bir nechta qator bo'lishi mumkin)
    confirm = State()

class TopUp(StatesGroup):
    amount = State()
    check_photo = State()

class Chat(StatesGroup):
    active = State()

class Admin(StatesGroup):
    broadcast = State()
    user_lookup = State()
    balance_adjust = State()
    set_price = State()
    set_ref_bonus = State()
    payment_info = State()
    payment_type = State()
    payment_number = State()
    set_channel = State()
