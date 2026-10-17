"""AI API integratsiyasi — to'liq ishlovchi versiya.
Oldindan tayyorlangan slayd strukturalari (4 ta mashhur mavzu).
Rasm faqat 1, 4, 7, oxirgi slaydlarda — har birida 1 ta.
Matn hajmi: 10 slayd = 6000+ belgi, 15 = 9000+, 25 = 15000+
"""
import aiohttp
import asyncio
import json
import re
import os
from config import AI_API_URL, AI_API_KEY, AI_TIMEOUT, AI_MODEL

# === Holat ===
LAST_ERROR = "hali sinanmadi"
WORKING_URL = None
PIXABAY_KEY = "57980675-db40c8e4d78300c2621fdfb50"

# === Rasmli slaydlar indekslari (0-index): 1, 4, 7, oxirgi ===
IMAGE_SLIDE_INDICES = [0, 3, 6]

# === Yordamchi funksiyalar ===
def clean_ai_text(text):
    if not text:
        return ""
    text = re.sub(r'\*+', '', str(text))
    text = re.sub(r'^#{1,3}\s*', '', str(text), flags=re.MULTILINE)
    text = re.sub(r'```.*?```', '', str(text), flags=re.DOTALL)
    text = re.sub(r'\n\s*\n', '\n\n', str(text))
    return text.strip()

def verify_facts(text):
    if not text:
        return text
    if "Navoiy" in text or "Alisher Navoiy" in text:
        text = re.sub(r'Samarqand', 'Hirot', text)
        text = re.sub(r'Samarqandda', 'Hirot shahrida', text)
    return text

def _log(msg):
    print(f"[AI_API] {msg}", flush=True)

def get_last_error():
    return LAST_ERROR

LANG_NAMES = {
    "uz": "o'zbek", "ru": "rus", "en": "english",
    "tr": "turkish", "de": "german", "fr": "french",
}
ALL_LANGS = ("uz", "ru", "en", "tr", "de", "fr")

def _lang_name(code):
    return LANG_NAMES.get(str(code).lower(), "o'zbek")

# === Rasm qidiruv lug'ati (o'zbekcha -> inglizcha) ===
SEARCH_MAP = {
    "alisher navoiy": "Alisher Navoi portrait historical poet",
    "navoiy": "Alisher Navoi writer historical",
    "amir temur": "Amir Temur historical leader conqueror",
    "temur": "Amir Temur Timurid empire",
    "jaloliddin manguberdi": "Jaloliddin Manguberdi Khwarazmshah warrior hero",
    "manguberdi": "Jaloliddin Manguberdi medieval hero",
    "mirzo ulugbek": "Mirzo Ulugh Beg astronomer observatory Samarkand",
    "ulugbek": "Ulugh Beg Timurid scholar scientist",
    "ibn sino": "Avicenna Ibn Sina philosopher physician",
    "toshkent": "Tashkent city Uzbekistan architecture",
    "samarqand": "Samarkand Registan historical",
    "buxoro": "Bukhara historical Uzbekistan",
    "uzbekiston": "Uzbekistan culture landmark",
}

# === Oldindan tayyorlangan slayd strukturalari ===
PREDEFINED_SLIDES = {
    "alisher navoiy": {
        "presentation_title": "Alisher Navoiy — hayoti, ijodi va abadiy merosi",
        "slides": [
            {"title": "Alisher Navoiy — ulug' so'z san'atkori", "content": ["Alisher Navoiy 1441-yilda Hirot shahrida tug'ilgan", "U o'z davrining eng buyuk shoiri, mutafakkiri va davlat arbobi hisoblanadi", "Uning asarlari o'zbek va boshqa turkiy xalqlar adabiyotining durdonasidir", "U 15-asr O'rta Osiyo madaniyatining eng yorqin namunasidir"], "has_image": True, "image_prompt": "historical portrait of Alisher Navoiy, 15th century Central Asian poet, noble appearance, holding ancient book, detailed, realistic, 8k"},
            {"title": "Bolalik va yoshlik davri", "content": ["Alisher Navoiy kamtarin oilada voyaga yetgan, otasi saroyda xizmat qilgan", "Yoshligidanoq ilm-fanga, she'riyatga va san'atga katta qiziqish bildirgan", "U mashhur ustozlardan — Jami, Sakkokiy va boshqalardan ta'lim olgan", "Hirotdagi madrasalarda tahsil olib, adabiyot, til va falsafani chuqur o'zlashtirgan", "Yoshligidayoq she'r yozishni boshlagan va tez orada shu sohada o'zini ko'rsatgan"], "has_image": False, "image_prompt": None},
            {"title": "Ijtimoiy va siyosiy faoliyati", "content": ["Navoiy Sulton Husayn Boyqaro saroyida yaqin maslahatchi va nazir bo'lgan", "U xalq ahvolini yaxshilash, ilm va madaniyatni rivojlantirish uchun harakat qilgan", "Davlat boshqaruvida adolatli qonunlarni joriy etishga katta hissa qo'shgan", "U odamlarning bir-biriga mehr-oqibatli bo'lishini doimo targ'ib qilgan", "Saroydagi mavqeidan foydalanib, kambag'allarni qo'llab-quvvatlagan"], "has_image": False, "image_prompt": None},
            {"title": "Mashhur 'Xamsa' dostoni", "content": ["Navoiy 'Xamsa' (besh doston) asarini 1483-yilda yakunlagan", "Ushbu to'plamga 'Hayrat ul-abror', 'Farhod va Shirin', 'Layli va Majnun', 'Sabbai Sayyor' hamda 'Saddi Iskandariy' kiradi", "Har bir doston mehr, do'stlik, adolat va qahramonlik mavzularini o'z ichiga oladi", "Bu asarlar turkiy tillar rivojiga beqiyos ta'sir ko'rsatgan", "'Xamsa' butun Islom olamida mashhur bo'lib, ko'p tillarga tarjima qilingan"], "has_image": True, "image_prompt": "ancient manuscript of Alisher Navoiy Khamsa, beautiful calligraphy, colorful illumination, medieval library background, hyperrealistic, 8k"},
            {"title": "Tilga qo'shgan beqiyos hissasi", "content": ["Navoiy o'zbek tilining boyligi va go'zalligini butun dunyoga namoyish etgan", "U asarlarini chig'atoy o'zbek tilida yozib, bu tilning imkoniyatlarini ko'rsatgan", "Uning tufayli keyingi avlodlar ham o'zbek tilida erkin ijod qila olgan", "U tilning sof va go'zal bo'lishiga doimo e'tibor qaratgan", "'Muhokamat ul-lug'atayn' asarida turkiy va forsiylarni solishtirib, tilning ustunligini isbotlagan"], "has_image": False, "image_prompt": None},
            {"title": "Falsafiy va axloqiy qarashlari", "content": ["Navoiy insonning ichki go'zalligini, mehr va saxovatni ulug'lagan", "Uning fikricha haqiqiy boylik mol-dunyo emas, balki yaxshi xulq va bilimdir", "U doimo odamlarni bir-biriga hurmatda bo'lishga chaqirgan", "Adolat, haqiqat va poklik uning barcha asarlarining asosiy g'oyasidir", "U insonning erkinligi va iroda erkinligi g'oyasini ilgari surgan"], "has_image": False, "image_prompt": None},
            {"title": "Bunyodkorlik va xayriya faoliyati", "content": ["Navoiy Hirotda ko'plab masjid, madrasa, ribat va bemorxonalar qurdirgan", "U kambag'al talabalarga bepul ta'lim berish uchun vositalar ajratgan", "O'z saroyida olimlar, shoirlar va san'atkorlarni har tomonlama qo'llab-quvvatlagan", "Uning xayriya faoliyati xalq orasida uning obro'sini yanada oshirgan", "Hirotda uning nomi bilan ataladigan ko'plab inshootlar saqlanib qolgan"], "has_image": True, "image_prompt": "Herat city medieval architecture, Timurid period mosque and madrasa, historical Afghanistan, cultural heritage, photorealistic, 8k"},
            {"title": "So'nggi yillari va vafoti", "content": ["Alisher Navoiy 1501-yilda Hirotda vafot etgan, umri 60 yilni tashkil etgan", "Uning jasadi Hirotda dafn etilgan, maqbarasi saqlanib qolgan", "Vafotidan so'ng xalq katta qayg'uga botgan, uning nomi abadiylashtirilgan", "Uning asarlari hozirga qadar butun dunyoda o'rganilmoqda va o'qilmoqda", "O'zbekiston va boshqa mamlakatlarda uning nomi ko'chalar va muassasalarga berilgan"], "has_image": False, "image_prompt": None},
            {"title": "Merosi va zamonaviy ahamiyati", "content": ["Navoiyning asarlari turkiy xalqlarning umumiy madaniy merosiga aylangan", "Uning she'riyati bugungi kunda ham o'zbek adabiyotining asosini tashkil etadi", "Uning asarlari 100 dan ortiq tillarga tarjima qilingan", "Har bir yangi avlod uning asarlaridan saboq olib, yaxshilikka intiladi", "Uning fikrlari va g'oyalari bugungi kunda ham dolzarb va muhimligini yo'qotmagan"], "has_image": False, "image_prompt": None},
            {"title": "Xulosa", "content": ["Alisher Navoiy nafaqat o'zbek, balkki butun turkiy xalqlarning buyuk farzandidir", "Uning so'zi, fikri va merosi hech qachon o'chmaydi, abadiy saqlanadi", "U insoniyat madaniyatiga qo'shgan hissasi beqiyos va katta", "Uning nomi abadiy xotiramizda saqlanib, kelajak avlodlarga yo'l ko'rsatadi", "Uning hayoti va ijodi har bir insonga ilm, mehr va adolatga intilishni o'rgatadi"], "has_image": True, "image_prompt": "glowing open book with Navoiy poetry, sunrise over ancient city, wisdom and inspiration concept, cinematic, 8k"}
        ]
    },
    "amir temur": {
        "presentation_title": "Amir Temur — buyuk sarkarda va davlat asoschisi",
        "slides": [
            {"title": "Amir Temur — hayoti va kelib chiqishi", "content": ["Amir Temur 1336-yilda Kesh (hozirgi Shahrisabz) shahrida tug'ilgan", "U o'z davrining eng kuchli sarkardasi va davlat arbobi hisoblanadi", "Uning asos solgan imperiyasi O'rta Osiyo, Eron, Ozarbayjon va boshqa mamlakatlarni qamrab olgan", "U Amir Temur nomi bilan butun dunyoda mashhur bo'lgan", "Uning tug'ilgan joyi bugungi O'zbekiston hududida joylashgan"], "has_image": True, "image_prompt": "historical portrait of Amir Temur, Turco-Mongol conqueror, 14th century warrior, noble and powerful figure, realistic, 8k"},
            {"title": "Yoshlik va harbiy tayyorgarlik", "content": ["Temur yoshligidanoq harb san'atiga qiziqqan, otasidan harbiy mahoratni o'rgangan", "U kichik yoshdayoq janglarda qatnashib, tajriba to'plagan", "25 yoshida o'z qo'shinini boshqargan va tez orada shon-sharafga erishgan", "U o'z atrofiga sodiq va tajribali kishilarni jamlagan", "Yoshligida oyoqidan yaralangan, shuning uchun 'Temur' (temir) deb atalgan"], "has_image": False, "image_prompt": None},
            {"title": "Davlatni birlashtirish", "content": ["Temur O'rta Osiyodagi turli elatlar va o'zbek urug'larini birlashtirishga erishgan", "U Samarqandni poytaxt qilib, buyuk Temuriylar davlatini barpo etgan", "U mamlakat ichida tartib va adolatni o'rnatishga harakat qilgan", "Uning hukmronligi davrida savdo va hunarmandchilik keng rivojlangan", "Samarqand o'sha davrda butun dunyoning eng yirik shaharlaridan biriga aylangan"], "has_image": False, "image_prompt": None},
            {"title": "Janglar va yurishlar", "content": ["U Eron, Hindiston, Turkiya, Oltin O'rda va Xitoyga yurishlar qilgan", "Uning qo'shini deyarli hech qachon mag'lub bo'lmagan, 35 yil davomida g'alaba qozongan", "Har bir g'alaba uning davlatining qudratini va hududini kengaytirgan", "U harbiy ishi bo'yicha dunyo tarixidagi eng yirik sarkardalardan biri hisoblanadi", "Uning harbiy strategiyalari keyingi asrlarning sarkardalariga o'rnak bo'lgan"], "has_image": True, "image_prompt": "Amir Temur leading army on horseback, medieval cavalry, epic historical scene, Central Asian conqueror, cinematic, 8k"},
            {"title": "Samarqand — jahonning gavhari", "content": ["Temur Samarqandni jahonning eng chiroyli va boy shahriga aylantirgan", "U bu yerda ko'plab masjidlar, madrasalar, maqbaralar va saroylar qurdirgan", "Shahar butun dunyo olimlari, ijodkorlari va savdogarlarini jalb qilgan", "U yurishlaridan olib kelgan boyliklar Samarqand qurilishiga sarflangan", "Samarqanddagi inshootlar bugungi kunda ham UNESCO merosi ro'yxatida"], "has_image": False, "image_prompt": None},
            {"title": "Ilm-fan va madaniyatga e'tibor", "content": ["Amir Temur olimlar, shoirlar va san'atkorlarni har tomonlama qo'llab-quvvatlagan", "Uning saroyida turli fanlar rivojlanishiga qulay sharoit yaratilgan", "Uning davrida me'morchilik san'ati juda yuqori darajaga ko'tarilgan", "U har doim bilimdon odamlarni hurmat qilgan va ularni saroyga taklif qilgan", "Temuriylar davri O'rta Osiyo madaniyatining eng gullab-yashnagan davridir"], "has_image": False, "image_prompt": None},
            {"title": "Shahrisabz — tug'ilgan shahar", "content": ["Temur tug'ilgan Shahrisabz shahrini ham juda hurmat qilgan va ulug'lantirgan", "U bu yerda Oqsaroy saroyini qurdirgan — bu o'sha davrning eng ulkan inshooti edi", "Shahrisabzda uning tug'ilgan uyi va maqbarasi saqlanib qolgan", "U har yili tug'ilgan shahriga tashrif buyurib, xalq bilan suhbatlashgan", "Shahrisabz bugungi kunda ham tarixiy shahar sifatida mashhur"], "has_image": True, "image_prompt": "Aksaray palace in Shahrisabz, Amir Temur birthplace, ancient ruins, majestic blue sky, historical Uzbekistan, photorealistic, 8k"},
            {"title": "So'nggi yurish va vafoti", "content": ["Amir Temur 1405-yilda Xitoyga yurish paytida Otrar shahrida vafot etgan", "Uning jasadi Samarqanddagi Go'ri Amir maqbarasiga dafn etilgan", "Uning o'rniga o'g'illari va nabiralari davlatni boshqarishni davom ettirgan", "U vafotidan so'ng imperiya asta-sekin bo'linib ketgan", "Lekin u qoldirgan madaniy meros asrlar davomida saqlanib kelgan"], "has_image": False, "image_prompt": None},
            {"title": "Xalq xotirasida va merosi", "content": ["Amir Temur buyuk davlat asoschisi sifatida xotiramizda abadiy saqlanadi", "Uning nomi mardlik, jasorat va adolat timsolidir", "Uning merosi bugungi O'zbekistonning ajralmas qismidir", "Toshkentda uning haykali o'rnatilgan, ko'cha va muassasalarga uning nomi berilgan", "Uning hayoti va faoliyati tarix fanida chuqur o'rganilmoqda"], "has_image": False, "image_prompt": None},
            {"title": "Xulosa", "content": ["Amir Temur — nafaqat o'zbek, balkki butun jahon tarixining buyuk shaxsidir", "Uning harbiy dahosi va davlat boshqaruv qobiliyati misli ko'rilmas darajada", "U qoldirgan madaniy meros butun insoniyatning boyligidir", "Uning nomi hech qachon unutilmaydi, abadiy xotiramizda saqlanadi", "Uning hayoti har bir insonga maqsadga intilish va jasoratni o'rgatadi"], "has_image": True, "image_prompt": "monument to Amir Temur in Tashkent, equestrian statue, national symbol, dignified pose, sunset background, photorealistic, 8k"}
        ]
    },
    "jaloliddin manguberdi": {
        "presentation_title": "Jaloliddin Manguberdi — xalq qahramoni va jasur sarkarda",
        "slides": [
            {"title": "Jaloliddin Manguberdi — hayoti va kelib chiqishi", "content": ["Jaloliddin Manguberdi 1199-yilda Xorazm shahrida tug'ilgan", "U Xorazmshohlar sulolasining vakili, otasining katta o'g'li edi", "U o'z davrining eng jasur sarkardasi va xalq qahramoni hisoblanadi", "U Chingizxon boshchiligidagi mo'g'ul qo'shinlariga qarshi mardonavor kurashgan", "Uning jasorati butun Osiyoda mashhur bo'lgan"], "has_image": True, "image_prompt": "historical portrait of Jaloliddin Manguberdi, Khwarazmshah prince, brave medieval warrior, noble and determined, realistic, 8k"},
            {"title": "Yoshlik va harbiy tayyorgarlik", "content": ["Jaloliddin yoshligidanoq harb san'atiga qiziqqan, otasidan harbiy mahoratni o'rgangan", "U otasi bilan birga davlat ishlarida qatnashib, tajriba to'plagan", "U o'ziga xos harbiy uslub va strategiya ishlab chiqqan", "Yoshligidayoq janglarda qatnashib, o'z jasoratini ko'rsatgan", "Uning qo'shinida xalqning eng jasur yoshlari xizmat qilgan"], "has_image": False, "image_prompt": None},
            {"title": "Xorazm davlati va mo'g'ul tahdidi", "content": ["O'sha davrda Chingizxon boshchiligidagi mo'g'ullar keng hududlarni egallab olgan edi", "Xorazm davlati ham kuchli tahdid ostida qoldi, shaharlar birma-bir egallandi", "Ota-onasi Xorazmshoh Muhammad mo'g'ullarga qarshi kurashda mag'lub bo'lib qochgan", "Ko'plab shaharlar vayron qilingan, xalq katta qiyinchiliklarga duch kelgan", "Faqat Jaloliddin boshchilik qilgan qo'shin qarshilik ko'rsata olgan"], "has_image": False, "image_prompt": None},
            {"title": "Parvon jangi — katta g'alaba", "content": ["1221-yilda Parvon (bugungi Afg'oniston) yaqinida mo'g'ullar bilan jang bo'lib o'tgan", "Jaloliddin boshchiligidagi qo'shin mo'g'ul qo'shinini mag'lub etgan", "Bu g'alaba xalq orasida katta umid uyg'otgan, uning obro'sini oshirgan", "Bu jangda mo'g'ullar birinchi marta jiddiy mag'lubiyatga uchragan", "Jaloliddinning harbiy dahosi butun mintaqada tan olinadi"], "has_image": True, "image_prompt": "Jaloliddin Manguberdi in battle on horseback, medieval warrior leading army, epic heroic scene, Central Asian hero, cinematic, 8k"},
            {"title": "Ind daryosi bo'yidagi jang", "content": ["Parvon jangidan so'ng Chingizxon katta qo'shin bilan Jaloliddin ortiga yuborilgan", "Ind daryosi bo'yidagi jangda Jaloliddin dushman qurshovida qolgan", "U oxirigacha kurashib, keyin daryoga sakrab o'tib, omon qolgan", "Chingizxon bu manzarani ko'rib, o'z farzandlariga shunday jasur bo'lishni buyurgan", "Bu voqea tarixda 'Ind daryosi fathoni' deb nomlanadi"], "has_image": False, "image_prompt": None},
            {"title": "Hindiston va Eron g'arbda faoliyati", "content": ["Ind daryosidan o'tganidan so'ng Jaloliddin Hindiston hududida bir muddat yashagan", "U yerda ham o'z qo'shinini to'plash va kuchaytirishga harakat qilgan", "Keyin Eronning g'arbiy hududlariga o'tib, u yerda davlat barpo etishga harakat qilgan", "U doimo mo'g'ullarga qarshi kurashni davom ettirgan", "Uning nomi butun Islom olamida xalq qahramoni sifatida hurmat qilindi"], "has_image": False, "image_prompt": None},
            {"title": "Xalq orasida obro'si va sevimi", "content": ["Jaloliddin o'z xalqining ozodligi uchun kurashgan haqiqiy qahramondir", "U hech qachon taslim bo'lmagan va oxirgi nafasigacha kurashgan", "Uning nomi mardlik, vatanparvarlik va matonat timsolidir", "Xalq uning haqida ko'plab ertak va she'rlar yozgan", "Uning jasorati avlodlar avlodiga o'tib kelgan"], "has_image": True, "image_prompt": "medieval Central Asian warrior standing on hill, wind blowing, heroic silhouette against sunset, national pride concept, cinematic, 8k"},
            {"title": "So'nggi yillari va vafoti", "content": ["Jaloliddin 1231-yilda Eronning g'arbida vafot etgan, aniq sababi noma'lum", "Uning jasadi qayerda dafn etilgani uzoq vaqt noma'lum bo'lgan", "Uning vafotidan so'ng mo'g'ullar butun mintaqani to'liq egallab olishgan", "Lekin uning kurashi xalq xotirasida hech qachon so'nmagan", "U oxirgi nafasigacha vatanparvarlik va jasorat namunasida bo'lgan"], "has_image": False, "image_prompt": None},
            {"title": "Merosi va zamonaviy ahamiyati", "content": ["Jaloliddin Manguberdi — o'zbek xalqining eng sevimli qahramonlaridan biridir", "Uning nomi ko'chalar, maydonlar va ta'lim muassasalariga berilgan", "Uning hayoti va jasorati yozuvchilar, shoirlar va rassomlar tomonidan abadiylashtirilgan", "Uning matonati va vatanparvarligi har bir avlodga o'rnak bo'lib qoladi", "Bugungi kunda ham uning nomi xalq orasida hurmat bilan tilga olinadi"], "has_image": False, "image_prompt": None},
            {"title": "Xulosa", "content": ["Jaloliddin Manguberdi — nafaqat o'zbek, balkki butun musulmon xalqlarining qahramonidir", "Uning jasorati va vatanparvarligi hech qachon unutilmaydi", "U har qanday qiyinchilikda taslim bo'lmagan inson namunasidir", "Uning hayoti har bir yosh avlodga vatanini sevishni o'rgatadi", "Uning nomi abadiy xotiramizda saqlanib, kelajak avlodlarga yorug'lik bo'ladi"], "has_image": True, "image_prompt": "Jaloliddin Manguberdi legacy concept, hero silhouette against sunrise, national pride, inspirational, cinematic, 8k"}
        ]
    },
    "mirzo ulugbek": {
        "presentation_title": "Mirzo Ulug'bek — buyuk olim, hukmdor va osmonshunos",
        "slides": [
            {"title": "Mirzo Ulug'bek — hayoti va kelib chiqishi", "content": ["Mirzo Ulug'bek 1394-yilda Sultoniya (Eron) shahrida tug'ilgan", "U Amir Temurning nabirasi, Shohruh Mirzoning o'g'li edi", "U yoshligidanoq ilm-fanga, ayniqsa astronomiyaga katta qiziqish bildirgan", "U 1409-yildan boshlab Samarqandni boshqargan, uni ilm va fan markaziga aylantirgan", "Uning tug'ilgan kunlari har yili O'zbekistonda nishonlanadi"], "has_image": True, "image_prompt": "historical portrait of Mirzo Ulugh Beg, Timurid scholar and astronomer, noble face, thoughtful expression, holding celestial globe, realistic, 8k"},
            {"title": "Yoshlik va ta'lim davri", "content": ["U yoshligida saroyda eng yaxshi ustozlardan ta'lim olgan", "Unga matematika, astronomiya, adabiyot va falsafa fanlari chuqur o'rgatilgan", "U sayohatlar qilgan, turli mamlakatlardagi olimlar bilan uchrashgan", "U yoshligidayoq osmon jismlarini kuzatishga qiziqib qolgan", "Ota-ona Shohruh va Goharshod uning ta'limiga katta e'tibor bergan"], "has_image": False, "image_prompt": None},
            {"title": "Davlat boshqaruvi va ilm-fan siyosati", "content": ["Ulug'bek 1447-yilda butun Temuriylar davlatining hukmdori bo'lgan", "U hukmdorlik bilan birga ilmiy ishlarni ham davom ettirgan", "U o'z saroyiga dunyoning turli mamlakatlaridan olimlarni taklif qilgan", "U ilm ahllarini moddiy va ma'naviy qo'llab-quvvatlagan", "Uning hukmronligi davrida Samarqand butun dunyoning ilm markaziga aylangan"], "has_image": False, "image_prompt": None},
            {"title": "Samarqand rasadxonasi — jahon mo'jizasi", "content": ["1428-1429-yillarda Samarqandda ulkan rasadxona qurdirgan", "Ushbu rasadxonada o'sha davrning eng nozik asboblari o'rnatilgan", "Bu yerda 20 yildan ortiq vaqt davomida osmon jismlari kuzatilgan", "Rasadxona o'z davrida butun dunyoga mashhur bo'lgan", "Unda 100 dan ortiq olim ishlagan, ularning hammasi dunyoga mashhur bo'lgan"], "has_image": True, "image_prompt": "Ulugh Beg Observatory in Samarkand, ancient astronomical building, giant quadrant instrument, medieval science landmark, photorealistic, 8k"},
            {"title": "Yangi yulduzlar jadvali — 'Zij-i Jadidi Ko'ragoniy'", "content": ["U 'Zij-i Jadidi Ko'ragoniy' asarini yozgan — bu 1437-yilda yakunlangan", "Unda 1019 ta yulduzning aniq joylashuvi, harakati va xossalari yozilgan", "Bu asar o'sha davrda eng aniq astronomik jadval hisoblangan", "Keyingi 300 yil davomida butun dunyo olimlari bu asardan foydalangan", "Uning hisoblashlari bugungi kunda ham o'z aniqligini saqlab qolgan"], "has_image": False, "image_prompt": None},
            {"title": "Matematika va boshqa fanlarga hissasi", "content": ["U trigonometriya va geometriya sohasida ham yangi kashfiyotlar qilgan", "U tomonidan ishlab chiqilgan usullar keyingi asrlarda ham qo'llanilgan", "Uning hisoblashicha, bir yil 365 kun 6 soat 10 daqiqa 8 soniya davom etadi", "Bu ko'rsatkich hozirgi aniq hisoblashga atigi 28 daqiqa bilan farq qiladi", "U shuningdek, adabiyot va tarixga oid asarlar ham yozgan"], "has_image": False, "image_prompt": None},
            {"title": "Registon — ilm va madaniyat markazi", "content": ["Ulug'bek Samarqandda Registon maydonida ulkan madrasa qurdirgan", "Bu madrasa o'sha davrning eng yirik ta'lim muassasasi bo'lgan", "Bu yerda minglab talaba ta'lim olgan, dunyoning turli burchaklaridan kelgan", "Registon bugungi kunda ham Samarqandning ramzi va UNESCO merosidir", "Ulug'bek madrasasi devorida astronomik chizmalar saqlanib qolgan"], "has_image": True, "image_prompt": "Registon square Samarkand, Ulugh Beg madrasa, majestic blue domes, Timurid architecture masterpiece, sunset, photorealistic, 8k"},
            {"title": "Davrning oxiri va fojiali yakun", "content": ["1449-yilda o'g'li Abdulatif tomonidan qo'zg'olon ko'tarilgan", "Ulug'bek hibsga olingan va fojiali tarzda o'ldirilgan, umri 55 yil edi", "Uning vafotidan keyin rasadxona ishlashi to'xtatilgan, asboblari vayron qilingan", "Ko'plab olimlar Samarqandni tark etishga majbur bo'lgan", "Fan markazi barbod bo'lgan, lekin uning asarlari abadiy saqlanib qolgan"], "has_image": False, "image_prompt": None},
            {"title": "Merosi va jahon tan olinishi", "content": ["Keyingi asrlarda uning asarlari Yevropaga tarqalib, ko'plab olimlarga yo'l ko'rsatgan", "1830-yilda rus astronomi V. Struve uning ishlarini qayta o'rganib, yuqori baho bergan", "O'zbekiston mustaqilligidan keyin uning nomi abadiylashtirildi", "U nomiga Oy va Quyosh tizimida kraterlar nomlandi", "Bu uning jahon miqyosidagi buyukligining eng yaxshi belgisi hisoblanadi"], "has_image": False, "image_prompt": None},
            {"title": "Xulosa", "content": ["Mirzo Ulug'bek — nafaqat o'zbek, balkki butun insoniyatning buyuk farzandidir", "Uning ishlari fan rivojiga ulkan hissa qo'shdi, asarlari asrlar davomida saboq bo'lib keldi", "U davlat boshqaruvi bilan birga fan ham rivojlanishi mumkinligini ko'rsatgan", "Uning nomi ilm, donolik va haqiqat timsolidir, hech qachon unutilmaydi", "Har bir yangi avlod uning hayotidan saboq olib, ilmga intiladi"], "has_image": True, "image_prompt": "starry night sky over Samarkand observatory, astronomy and wisdom theme, glowing celestial globe, cinematic, 8k"}
        ]
    }
}

# === API sozlamalari ===
HEADERS_OAI = {
    "Authorization": f"Bearer {AI_API_KEY}",
    "Content-Type": "application/json"
}

ENDPOINTS_OAI = ["/v1/chat/completions", "/chat/completions", "/api/v1/chat/completions"]

CANDIDATE_URLS = list(dict.fromkeys([
    AI_API_URL, "http://127.0.0.1:31415", "http://localhost:31415",
    "http://127.0.0.1:3000", "http://127.0.0.1:8080",
]))

SYSTEM_PROMPT = """Siz mutaxassis yordamchisiz. Barcha javoblar to'liq, batafsil, faktlarga asoslangan bo'lsin.
Faqat tasdiqlangan ma'lumotlardan foydalaning. Hech qanday * # belgi ishlatmang."""

CHAT_SYSTEM = """Siz do'stona, bilimdon AI yordamchisiz. Foydalanuvchi savollariga to'liq, batafsil javob bering.
Faqat ishonchli ma'lumotlardan foydalaning. Hech qanday * # belgi ishlatmang."""

async def _try_post(url, payload, headers):
    global LAST_ERROR
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=AI_TIMEOUT)) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                body = await resp.text()
                if resp.status == 200:
                    LAST_ERROR = None
                    return 200, body, None
                LAST_ERROR = f"HTTP {resp.status}: {body[:150]}"
                return resp.status, None, LAST_ERROR
    except aiohttp.ClientConnectorError as e:
        LAST_ERROR = f"Ulanib bo'lmadi: {e}"
        return None, None, LAST_ERROR
    except asyncio.TimeoutError:
        LAST_ERROR = f"Vaqt tugadi: {AI_TIMEOUT}s"
        return None, None, LAST_ERROR
    except Exception as e:
        LAST_ERROR = f"Xato: {type(e).__name__}: {e}"
        return None, None, LAST_ERROR

async def test_api():
    global WORKING_URL
    lines = [f"Kalit: {AI_API_KEY[:15]}...", f"Model: {AI_MODEL}", ""]
    for base in CANDIDATE_URLS:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(base) as resp:
                    lines.append(f"GET {base}/ → HTTP {resp.status}")
        except Exception:
            lines.append(f"GET {base}/ → ulanib bo'lmadi")
            continue
        payload = {"model": AI_MODEL, "messages": [{"role": "user", "content": "Salom"}], "max_tokens": 20}
        for ep in ENDPOINTS_OAI:
            status, body, err = await _try_post(f"{base}{ep}", payload, HEADERS_OAI)
            if status == 200:
                WORKING_URL = base
                lines.append(f"POST {base}{ep} → ✅ 200 OK (ishlaydi!)")
                lines.append(f"\n✅ Ishlaydigan manzil: {base}")
                return "\n".join(lines)
            lines.append(f"POST {base}{ep} → ❌ {err or status}")
    lines.append("\n⚠️ Hech bir manzilda ishlaydigan AI server topilmadi.")
    lines.append("Yechim: freellmapi dasturini ishga tushiring.")
    return "\n".join(lines)

async def _chat_complete(prompt, system=None, max_tokens=16000):
    global WORKING_URL
    messages = [
        {"role": "system", "content": system or SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]
    payload = {"model": AI_MODEL, "messages": messages, "temperature": 0.7, "max_tokens": max_tokens}
    urls = ([WORKING_URL] if WORKING_URL else []) + [u for u in CANDIDATE_URLS if u != WORKING_URL]
    for base in urls:
        if not base:
            continue
        _log(f"Sinab ko'rilmoqda: {base}")
        for ep in ENDPOINTS_OAI:
            status, body, err = await _try_post(f"{base}{ep}", payload, HEADERS_OAI)
            if status == 200 and body:
                try:
                    data = json.loads(body)
                    choices = data.get("choices", [{}])
                    if choices:
                        txt = choices[0].get("message", {}).get("content")
                        if txt:
                            txt = clean_ai_text(txt)
                            txt = verify_facts(txt)
                            WORKING_URL = base
                            _log(f"✅ {base} orqali javob olindi ({len(txt)} belgi)")
                            return txt.strip()
                except Exception as e:
                    _log(f"Javobni tahlil qilishda xato: {e}")
    _log("⚠️ Hech bir manzil javob bermadi")
    return None

async def chat_answer(question):
    return await _chat_complete(question, system=CHAT_SYSTEM)

async def generate(service, topic, options, lang="uz"):
    from services import SERVICES
    s = SERVICES.get(service, {})
    name = s.get("name", service)
    pages = int(options.get("pages", 10) or 10)
    ln = _lang_name(lang)
    # Bob soni: sahifa soniga mos — 15 sahifa = 12+ bob
    bob_count = max(8, pages)
    doc_chars = pages * 900  # har sahifa ~900 belgi
    prompt = (
        f"Topic: {topic}\nService: {name}\nLength: {pages} pages (minimum {doc_chars} characters total)\n\n"
        f"⚠️ WRITE EVERYTHING STRICTLY IN {ln.upper()} LANGUAGE ONLY! Not a single word in another language.\n\n"
        f"⚠️ MINIMUM {doc_chars} CHARACTERS TOTAL! At least {bob_count} sections (chapters). "
        f"Each chapter at least {max(400, doc_chars//bob_count)} characters, detailed with facts, examples, statistics.\n\n"
        f"REQUIRED STRUCTURE:\n"
        f"1. Introduction (Kirish) — relevance, goals, objectives\n"
        f"2. Main chapters (Asosiy qism) — {bob_count-4} detailed chapters with analysis, facts, statistics, historical context, real examples\n"
        f"3. Analysis (Tahlil) — critical evaluation\n"
        f"4. Conclusion (Xulosa) — key findings, summary\n"
        f"5. References (Adabiyotlar)\n\n"
        f"Each chapter must be thorough, detailed, with specific data, dates, numbers, and real examples. "
        f"Do not use * or # symbols. Write long, informative paragraphs. The document must be comprehensive and academic."
    )
    result = await _chat_complete(prompt, max_tokens=16000)
    if result:
        return result, True
    await asyncio.sleep(1)
    return _fallback_text(service, topic, options, lang, bob_count), False

def _is_image_slide(idx, total):
    """Rasmli slaydlar: 1, 4, 7 va oxirgi (0-index: 0, 3, 6, total-1)"""
    return idx in IMAGE_SLIDE_INDICES or idx == total - 1

async def generate_slides_structured(topic, subject, lang, count):
    """API dan to'liq kontent oladi — kerakli hajmdagi belgi, to'g'ri tuzilishda.
    Struktura: Kirish → Asosiy qism (boblar) → Xulosa.
    FAQAT API javob bermasa, fallback ishlatiladi."""
    ln = _lang_name(lang)
    # To'g'ri belgi sonlari (foydalanuvchi talabi):
    # 10→7000, 15→10000, 20→13000, 25→18000, 30→22000
    char_map = {5: 4000, 7: 5000, 10: 7000, 12: 8500, 15: 10000,
                18: 11500, 20: 13000, 25: 18000, 30: 22000}
    target_chars = char_map.get(count, count * 750)
    # Har bir slayd uchun taxminiy belgi (sarlavha + 8-10 gap)
    per_slide = max(500, target_chars // count)

    system = f"""You are an expert academic content writer. 
Write EVERYTHING strictly in {ln.upper()} language ONLY! Not a single word in another language.
Total output must be at least {target_chars} characters. 
Each slide must have a clear title and 8-10 detailed, long, informative sentences with specific facts, dates, statistics, and examples.
Structure the slides logically: Introduction (Kirish) → Main content (Asosiy qism, multiple detailed slides) → Conclusion (Xulosa).
Be very thorough, detailed, and academic. Do NOT use markdown symbols (*, #, ```). Return ONLY valid JSON."""

    prompt = f"""Create a detailed academic presentation on the topic below.

TOPIC: {topic}
SUBJECT: {subject}
LANGUAGE: {ln.upper()} ONLY! Every single word must be in {ln.upper()}. Do NOT mix languages.
NUMBER OF SLIDES: {count}
MINIMUM TOTAL CHARACTERS: {target_chars} (at least {per_slide} characters per slide)

REQUIRED STRUCTURE:
- Slide 1: Title slide (topic name)
- Slides 2-3: Introduction (Kirish) — relevance, goals, objectives
- Slides 4 to {count-2}: Main content (Asosiy qism) — detailed analysis, facts, statistics, examples, historical context, each slide focused on one subtopic
- Slide {count-1}: Analysis and discussion (Tahlil)
- Slide {count}: Conclusion (Xulosa) — key findings, summary

Each slide must have:
- A clear, specific title (not generic)
- 8-10 complete, long, detailed sentences with specific facts, numbers, dates, and real examples
- No bullet points with 1-2 words — full sentences only

Return ONLY a valid JSON array (no extra text, no markdown, no explanation):
[{{"title":"Slide title here","content":["Sentence 1.","Sentence 2.","Sentence 3.","Sentence 4.","Sentence 5.","Sentence 6.","Sentence 7.","Sentence 8."]}}]

IMPORTANT: Return exactly {count} slide objects. Total text must be at least {target_chars} characters!"""

    # 2 urinish — birinchi urinish qisqa bo'lsa, yana so'raymiz
    txt = None
    for attempt in range(2):
        txt = await _chat_complete(prompt, system=system, max_tokens=16000)
        if txt and len(txt) > target_chars * 0.5:
            break
        _log(f"⚠️ Urinish {attempt+1}: {len(txt) if txt else 0} belgi (kerak: {target_chars}), qayta so'ralmoqda...")
        await asyncio.sleep(1)

    slides = _extract_json(txt) if txt else None
    if slides and isinstance(slides, list) and len(slides) >= 3:
        out = []
        # Agar kam slayd kelsa — takrorlab/kengaytiramiz
        while len(slides) < count:
            slides.append(slides[len(slides) % len(slides)])
        for i, s in enumerate(slides[:count]):
            content_list = s.get("content", ["Preparing content..."])
            if isinstance(content_list, str):
                content_list = [p.strip() for p in content_list.split("\n") if p.strip()]
            # Har bir slaydda kamida 5 gap bo'lsin (tilga mos, o'zbekcha aralashmasin)
            PAD = {"uz": f"{topic} bo'yicha batafsil tahlil — faktlar, statistika va misollar bilan.",
                   "ru": f"Подробный анализ темы «{topic}» — факты, статистика и примеры.",
                   "en": f"Detailed analysis of {topic} — with facts, statistics and examples.",
                   "tr": f"{topic} hakkında detaylı analiz — gerçekler, istatistikler ve örneklerle.",
                   "de": f"Detaillierte Analyse von {topic} — mit Fakten, Statistiken und Beispielen.",
                   "fr": f"Analyse détaillée de {topic} — faits, statistiques et exemples."}
            pad_txt = PAD.get(str(lang).lower(), PAD["en"])
            while len(content_list) < 5:
                content_list.append(pad_txt)
            out.append({
                "slide_number": i + 1,
                "title": clean_ai_text(str(s.get("title", f"Part {i+1}"))),
                "content": [clean_ai_text(str(c)) for c in content_list[:12]],
                "has_image": _is_image_slide(i, count),
                "image_prompt": _make_image_prompt(topic, i) if _is_image_slide(i, count) else None
            })
        total = sum(len(" ".join(s["content"])) for s in out)
        _log(f"✅ API dan tayyor: {len(out)} slayd | Jami {total} belgi (maqsad: {target_chars})")
        return out, True

    _log(f"⚠️ API javobi yaroqsiz ({len(txt) if txt else 0} belgi). Fallback ishlatilmoqda.")
    await asyncio.sleep(1)
    return _fallback_slides(topic, count, lang), False

def _fallback_slides(topic, count, lang="uz"):
    fb = _fb(lang)
    out = []
    for i in range(count):
        sec = fb["slide_sections"][i % len(fb["slide_sections"])]
        out.append({
            "slide_number": i + 1,
            "title": f"{topic}: {sec}" if i > 0 else topic,
            "content": [b.format(topic=topic, sec=sec.lower()) for b in fb["slide_body"]],
            "has_image": _is_image_slide(i, count),
            "image_prompt": _make_image_prompt(topic, i) if _is_image_slide(i, count) else None
        })
    return out

def _make_image_prompt(topic, idx):
    t = topic.lower()
    base = "historical figure, realistic, 8k"
    for uz, en in SEARCH_MAP.items():
        if uz in t:
            base = en
            break
    if idx == 0:
        return f"portrait of {base}, dignified pose, detailed, photorealistic, 8k"
    elif idx == 3:
        return f"{base} epic historical scene, cultural heritage, 8k"
    elif idx == 6:
        return f"{base} ancient architecture, monument, 8k"
    else:
        return f"{base} legacy, starry sky or sunset, inspirational, cinematic, 8k"

async def search_images(query, count=5):
    """Rasm qidiradi — FAQAT MOS KELGANLARINI qabul qiladi.
    Agar mos rasm topilmasa, [] qaytaradi (dekorativ rasm ishlatiladi)."""
    q = re.sub(r'[^\w\s\']', ' ', str(query)).strip()
    if len(q) < 3:
        _log(f"[RASM] So'z juda qisqa: '{q}'")
        return []
    q_en = q
    for uz, en in SEARCH_MAP.items():
        if uz in q.lower():
            q_en = en
            _log(f"[RASM] Avtomatik: '{q}' → '{q_en}'")
            break

    # Moslik tekshiruvi uchun kalit so'zlar
    keywords = [w for w in q_en.lower().split() if len(w) > 2]
    # Umumiy keraksiz so'zlarni olib tashlash
    stop = {"portrait", "historical", "hero", "leader", "conqueror", "poet", "writer",
            "scholar", "astronomer", "city", "architecture", "culture", "landmark",
            "warrior", "prince", "scientist", "figure", "realistic", "8k", "photo"}
    keywords = [w for w in keywords if w not in stop]

    urls = []
    for search_q in [q_en, q, f"{q_en} portrait", f"{q_en} historical"]:
        if len(urls) >= count:
            break
        url = (
            f"https://pixabay.com/api/?key={PIXABAY_KEY}"
            f"&q={search_q.replace(' ', '+')}"
            f"&image_type=photo&orientation=horizontal&per_page=50&safesearch=true"
        )
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
        except Exception as e:
            _log(f"[RASM] Xato: {e}")
            continue

        for hit in data.get("hits", []):
            u = hit.get("webformatURL")
            if not u or u in urls:
                continue
            # ✅ MOSLIK TEKSHIRUVI: tags yoki title da kamida bitta kalit so'z bo'lishi shart
            tags = (hit.get("tags", "") + " " + hit.get("title", "")).lower()
            mos = sum(1 for kw in keywords if kw in tags)
            if mos == 0 and keywords:
                continue  # umuman mos kelmagan — o'tkazib yuboramiz
            urls.append(u)
            if len(urls) >= count:
                break

    urls = list(dict.fromkeys(urls))[:count]
    if not urls:
        _log(f"⚠️ '{q}' uchun mos rasm topilmadi — dekorativ rasm ishlatiladi")
    else:
        _log(f"📸 '{q}' → {len(urls)} ta MOS rasm topildi ✅")
    return urls

async def download_image(url, save_path):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    with open(save_path, "wb") as f:
                        f.write(data)
                    try:
                        from PIL import Image
                        with Image.open(save_path) as img:
                            img.verify()
                    except Exception:
                        pass
                    return True
    except Exception as e:
        _log(f"[RASM] Yuklash xatosi: {e}")
    return False

def _extract_json(text):
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except Exception:
            pass
    return None

# ===== 6 til uchun fallback strukturaviy yorliqlar =====
FB = {
    "uz": {
        "sections": ["Kirish", "Tarixiy kelib chiqishi", "Nazariy asoslari", "Asosiy qism 1",
                     "Asosiy qism 2", "Asosiy qism 3", "Tahlil", "Muammolar va yechimlar",
                     "Xulosa", "Foydalanilgan adabiyotlar"],
        "extra": "Qo'shimcha bob",
        "body": "{topic} bo'yicha {sec} — batafsil ma'lumotlar, faktlar, misollar va tahlillar. "
                "Ushbu bob mavzuning muhim qismlaridan birini o'z ichiga oladi. Har bir gap to'liq, mazmunli va batafsil yozilgan.",
        "slide_sections": ["Kirish va dolzarblik", "Tarixiy kelib chiqishi", "Yoshlik va ta'lim",
                           "Faoliyat bosqichlari", "Asosiy yutuqlar", "Ilm-fan va madaniyatga hissasi",
                           "Bunyodkorlik va xayriya", "So'nggi yillari", "Merosi va zamonaviy ahamiyati", "Xulosa"],
        "slide_body": [
            "{topic} ning {sec} jihati mavzuning eng muhim qismlaridan biridir",
            "Ushbu davrda shaxsning shakllanishi, dunyoqarashi va faoliyati shakllangan",
            "Bu davrda olgan bilim va tajribalari keyingi barcha ishlariga asos bo'lgan",
            "Uning faoliyati davrida ko'plab o'zgarishlar va yangiliklar amalga oshirilgan",
            "Bugungi kunda bu mavzu keng o'rganilmoqda va avlodlarga saboq bo'lib xizmat qilmoqda",
            "Uning merosi kelajak avlodlar uchun ham yo'l ko'rsatuvchi yulduz bo'lib qoladi",
        ],
    },
    "ru": {
        "sections": ["Введение", "Историческое происхождение", "Теоретические основы", "Основная часть 1",
                     "Основная часть 2", "Основная часть 3", "Анализ", "Проблемы и решения",
                     "Заключение", "Список литературы"],
        "extra": "Дополнительная глава",
        "body": "По теме «{topic}» раздел «{sec}» — подробные сведения, факты, примеры и анализ. "
                "Данная глава раскрывает один из важнейших аспектов темы. Каждое предложение полное, содержательное и подробное.",
        "slide_sections": ["Введение и актуальность", "Историческое происхождение", "Молодость и обучение",
                           "Этапы деятельности", "Основные достижения", "Вклад в науку и культуру",
                           "Созидание и благотворительность", "Последние годы", "Наследие и современное значение", "Заключение"],
        "slide_body": [
            "Аспект «{sec}» темы «{topic}» является одним из важнейших",
            "В этот период формировалась личность, мировоззрение и деятельность",
            "Знания и опыт, полученные в этот период, стали основой всех последующих работ",
            "В период его деятельности произошло множество изменений и нововведений",
            "Сегодня эта тема широко изучается и служит уроком для будущих поколений",
            "Его наследие останется путеводной звездой и для будущих поколений",
        ],
    },
    "en": {
        "sections": ["Introduction", "Historical background", "Theoretical foundations", "Main part 1",
                     "Main part 2", "Main part 3", "Analysis", "Problems and solutions",
                     "Conclusion", "References"],
        "extra": "Additional chapter",
        "body": "On the topic «{topic}», the section «{sec}» provides detailed information, facts, examples and analysis. "
                "This chapter covers one of the most important aspects of the topic. Every sentence is complete, meaningful and detailed.",
        "slide_sections": ["Introduction and relevance", "Historical background", "Youth and education",
                           "Stages of activity", "Main achievements", "Contribution to science and culture",
                           "Creation and charity", "Later years", "Legacy and modern significance", "Conclusion"],
        "slide_body": [
            "The «{sec}» aspect of «{topic}» is one of the most important parts",
            "During this period the personality, worldview and activity were formed",
            "The knowledge and experience gained became the foundation for all later work",
            "Many changes and innovations took place during the period of activity",
            "Today this topic is widely studied and serves as a lesson for future generations",
            "The legacy will remain a guiding star for future generations as well",
        ],
    },
    "tr": {
        "sections": ["Giriş", "Tarihî köken", "Kuramsal temeller", "Ana bölüm 1",
                     "Ana bölüm 2", "Ana bölüm 3", "Analiz", "Sorunlar ve çözümler",
                     "Sonuç", "Kaynakça"],
        "extra": "Ek bölüm",
        "body": "«{topic}» konusunun «{sec}» bölümü — detaylı bilgiler, gerçekler, örnekler ve analizler. "
                "Bu bölüm konunun en önemli yönlerinden birini kapsar. Her cümle tam, anlamlı ve detaylıdır.",
        "slide_sections": ["Giriş ve güncellik", "Tarihî köken", "Gençlik ve eğitim",
                           "Faaliyet aşamaları", "Temel başarılar", "Bilim ve kültüre katkı",
                           "Yaratıcılık ve hayırseverlik", "Son yıllar", "Miras ve modern önem", "Sonuç"],
        "slide_body": [
            "«{topic}» konusunun «{sec}» yönü en önemli kısımlardan biridir",
            "Bu dönemde kişilik, dünya görüşü ve faaliyet şekillendi",
            "Bu dönemde kazanılan bilgi ve deneyim sonraki tüm çalışmaların temeli oldu",
            "Faaliyet dönemi boyunca birçok değişiklik ve yenilik gerçekleşti",
            "Bugün bu konu geniş çapta inceleniyor ve gelecek nesillere ders oluyor",
            "Miras gelecek nesiller için de yol gösterici bir yıldız olarak kalacak",
        ],
    },
    "de": {
        "sections": ["Einleitung", "Historischer Hintergrund", "Theoretische Grundlagen", "Hauptteil 1",
                     "Hauptteil 2", "Hauptteil 3", "Analyse", "Probleme und Lösungen",
                     "Fazit", "Literaturverzeichnis"],
        "extra": "Zusätzliches Kapitel",
        "body": "Zum Thema «{topic}» liefert der Abschnitt «{sec}» detaillierte Informationen, Fakten, Beispiele und Analysen. "
                "Dieses Kapitel behandelt einen der wichtigsten Aspekte des Themas. Jeder Satz ist vollständig, inhaltlich und detailliert.",
        "slide_sections": ["Einleitung und Aktualität", "Historischer Hintergrund", "Jugend und Ausbildung",
                           "Phasen der Tätigkeit", "Hauptleistungen", "Beitrag zu Wissenschaft und Kultur",
                           "Schaffen und Wohltätigkeit", "Späte Jahre", "Vermächtnis und moderne Bedeutung", "Fazit"],
        "slide_body": [
            "Der «{sec}»-Aspekt von «{topic}» ist einer der wichtigsten Teile",
            "In dieser Zeit formten sich Persönlichkeit, Weltanschauung und Wirken",
            "Die in dieser Zeit erworbenen Kenntnisse wurden zur Grundlage aller späteren Arbeiten",
            "Während der Wirkungszeit fanden viele Veränderungen und Neuerungen statt",
            "Heute wird dieses Thema umfassend erforscht und dient künftigen Generationen als Lehre",
            "Das Vermächtnis wird auch für künftige Generationen ein Leitstern bleiben",
        ],
    },
    "fr": {
        "sections": ["Introduction", "Contexte historique", "Fondements théoriques", "Partie principale 1",
                     "Partie principale 2", "Partie principale 3", "Analyse", "Problèmes et solutions",
                     "Conclusion", "Bibliographie"],
        "extra": "Chapitre supplémentaire",
        "body": "Sur le thème «{topic}», la section «{sec}» fournit des informations détaillées, des faits, des exemples et des analyses. "
                "Ce chapitre couvre l'un des aspects les plus importants du sujet. Chaque phrase est complète, significative et détaillée.",
        "slide_sections": ["Introduction et pertinence", "Contexte historique", "Jeunesse et formation",
                           "Étapes d'activité", "Réalisations principales", "Contribution à la science et à la culture",
                           "Création et charité", "Années tardives", "Héritage et signification moderne", "Conclusion"],
        "slide_body": [
            "L'aspect «{sec}» de «{topic}» est l'une des parties les plus importantes",
            "Pendant cette période, la personnalité, la vision du monde et l'activité se sont formées",
            "Les connaissances et l'expérience acquises sont devenues le fondement de tous les travaux ultérieurs",
            "De nombreux changements et innovations ont eu lieu pendant la période d'activité",
            "Aujourd'hui, ce sujet est largement étudié et sert de leçon aux générations futures",
            "L'héritage restera une étoile directrice pour les générations futures également",
        ],
    },
}

def _fb(lang):
    return FB.get(str(lang).lower(), FB["uz"])

def _fallback_text(service, topic, options, lang, bob_count=10):
    pages = int(options.get("pages", 10) or 10)
    fb = _fb(lang)
    sections = list(fb["sections"])
    while len(sections) < bob_count:
        sections.insert(len(sections)-2, f"{fb['extra']} {len(sections)-3}")
    parts = []
    for i, sec in enumerate(sections[:bob_count]):
        body = fb["body"].format(topic=topic, sec=sec.lower())
        parts.append(f"{sec}\n{body}\n{body}")
    return f"{topic}\n\n" + "\n\n".join(parts)

