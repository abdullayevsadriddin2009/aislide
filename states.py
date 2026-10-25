from aiogram.fsm.state import State, StatesGroup

class Creation(StatesGroup):
    service = State()
    topic = State()
    subject = State()
    language = State()
    design = State()
    slide_count = State()
    slide_design = State()
    option = State()
    format = State()
    author = State()   # ✅ Muallif ismi (bir nechta qator bo'lishi mumkin)
    confirm = State()
    essay_outline = State()   # ✅ Essay reja bosqichi
    
    # ===== REFERAT UCHUN MAXSUS STATE'LAR =====
    ref_subject = State()      # Fan nomi
    ref_institution = State()  # O'quv muassasasi (Universitet/Institut)
    ref_faculty = State()      # Fakultet
    ref_dept = State()         # Kafedra
    ref_author = State()       # Ijro etuvchi (Talaba)
    ref_checker = State()      # Tekshiruvchi (O'qituvchi)

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
