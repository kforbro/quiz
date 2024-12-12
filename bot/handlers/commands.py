import json

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, PollAnswer, User, FSInputFile
from aiogram.utils.deep_linking import create_start_link
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.payload import decode_payload
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bot.common import SelectQuizCallbackData, StartQuizCallbackData, StopQuizCallbackData, InviteQuizCallbackData, \
    StatsQuizCallbackData
from bot.db import Quiz
from bot.db.models import Stat
from bot.keyboards import generate_main_menu, generate_my_quizzes, generate_my_quiz
from bot.utils.qrcode_api import generate_qr_code

router = Router(name="commands-router")

current_quizzes = {}
temporary_quiz_data = {}

usernames = {}


def get_clickable_name(user: User):
    if user.id in usernames:
        if user.username:
            return f"<a href='https://t.me/{user.username}'>{usernames[user.id]}</a>"
        else:
            return f"{usernames[user.id]} ({user.full_name})"
    else:
        if user.username:
            return f"<a href='https://t.me/{user.username}'>{user.full_name}</a>"
        else:
            return f"{user.full_name}"


class QuizParticipation(StatesGroup):
    waiting_for_name = State()
    waiting_for_answer = State()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, command: CommandObject, state: FSMContext):
    await message.bot.send_sticker(message.from_user.id, sticker=FSInputFile("sticker.tgs"))
    quiz_id = 0
    try:
        quiz_id = int(decode_payload(command.args))

        # Проверяем наличие викторины в базе данных
        quiz = await session.get(Quiz, quiz_id)
        if not quiz:
            await message.answer(f"Викторина с ID {quiz_id} не найдена.")
            return

        # Проверяем, начата ли викторина
        if quiz.active:
            await message.answer("Викторина уже началась.")
            return

        # Добавляем студента в список участников викторины
        if quiz_id not in current_quizzes:
            current_quizzes[quiz_id] = {"participants": {}}

        # Сохраняем quiz_id в FSM
        await state.update_data(quiz_id=quiz_id)

        # Запрашиваем имя пользователя
        await message.answer("Пожалуйста, введите ваше имя и группу:")
        await state.set_state(QuizParticipation.waiting_for_name)
    except:
        await message.answer(
            "Добро пожаловать в Quiz Wings! Здесь можно участвовать в викторинах и создавать свои ✈️",
            reply_markup=generate_main_menu()
        )


class QuizCreation(StatesGroup):
    waiting_for_quiz_name = State()
    waiting_for_quiz_description = State()
    waiting_for_question_text = State()
    waiting_for_question_type = State()
    waiting_for_question_options = State()
    waiting_for_correct_answer = State()


# Начало создания викторины
@router.callback_query(F.data == "my_quizzes")
async def my_quizzes(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    db_query = await session.execute(select(Quiz).filter_by(user_id=callback.from_user.id).order_by(Quiz.id))
    quizzes = db_query.scalars().all()
    await callback.bot.send_sticker(callback.from_user.id, sticker=FSInputFile("sticker.tgs"))
    await callback.message.answer("Ваши викторины:", reply_markup=generate_my_quizzes(quizzes))


# Начало создания викторины
@router.message(Command("my_quizzes"))
async def my_quizzes(message: Message, state: FSMContext, session: AsyncSession):
    await message.delete()
    db_query = await session.execute(select(Quiz).filter_by(user_id=message.from_user.id).order_by(Quiz.id))
    quizzes = db_query.scalars().all()
    await message.answer("Ваши викторины:", reply_markup=generate_my_quizzes(quizzes))


# Начало создания викторины
@router.callback_query(SelectQuizCallbackData.filter())
async def select_my_quiz(callback: CallbackQuery, callback_data: SelectQuizCallbackData, state: FSMContext,
                         session: AsyncSession):
    db_query = await session.execute(select(Quiz).filter_by(id=callback_data.quiz_id, user_id=callback.from_user.id))
    quiz = db_query.scalar()
    await callback.message.answer(f"Викторина {quiz.id}: {quiz.name}",
                                  reply_markup=generate_my_quiz(quiz))


# Начало создания викторины
@router.callback_query(StartQuizCallbackData.filter())
async def start_my_quiz(callback: CallbackQuery, callback_data: StartQuizCallbackData, state: FSMContext,
                        session: AsyncSession):
    db_query = await session.execute(select(Quiz).filter_by(id=callback_data.quiz_id, user_id=callback.from_user.id))
    quiz = db_query.scalar()
    if not quiz:
        await callback.message.answer(f"Викторина с ID {quiz.id} не найдена.")
        return

    if quiz.user_id != callback.from_user.id:
        await callback.message.answer(f"Это не Ваша викторина.")
        return

    # Устанавливаем статус викторины как активный
    quiz.active = True
    await session.commit()

    # Проверяем, есть ли участники
    if quiz.id not in current_quizzes or not current_quizzes[quiz.id]["participants"]:
        await callback.message.answer("Нет участников для начала викторины.")
        return

    # Отправляем первый вопрос всем участникам
    quiz_data = json.loads(quiz.json)
    questions = quiz_data.get("questions", [])

    if not questions:
        await callback.message.answer("Викторина не содержит вопросов.")
        return

    # Отправляем первый вопрос каждому участнику
    for user_id in current_quizzes[quiz.id]["participants"]:
        first_question = questions[0]
        await send_question(callback.bot, user_id, first_question, 1)


# Начало создания викторины
@router.callback_query(StopQuizCallbackData.filter())
async def stop_my_quiz(callback: CallbackQuery, callback_data: StopQuizCallbackData, state: FSMContext,
                       session: AsyncSession):
    db_query = await session.execute(select(Quiz).filter_by(id=callback_data.quiz_id, user_id=callback.from_user.id))
    quiz = db_query.scalar()
    if not quiz:
        await callback.message.answer(f"Викторина с ID {quiz.id} не найдена.")
        return

    if quiz.user_id != callback.from_user.id:
        await callback.message.answer(f"Это не Ваша викторина.")
        return
    # Устанавливаем статус викторины как активный
    quiz.active = False
    await session.commit()
    if quiz.id in current_quizzes:
        current_quizzes.pop(quiz.id)


# Начало создания викторины
@router.callback_query(InviteQuizCallbackData.filter())
async def invite_quiz(callback: CallbackQuery, callback_data: InviteQuizCallbackData, state: FSMContext,
                      session: AsyncSession):
    db_query = await session.execute(select(Quiz).filter_by(id=callback_data.quiz_id, user_id=callback.from_user.id))
    quiz = db_query.scalar()
    if not quiz:
        await callback.message.answer(f"Викторина с ID {quiz.id} не найдена.")
        return

    if quiz.user_id != callback.from_user.id:
        await callback.message.answer(f"Это не Ваша викторина.")
        return

    link = await create_start_link(callback.bot, str(quiz.id), True)
    await callback.message.answer(f"Ссылка для приглашения: {link}")
    qr_code_io = generate_qr_code(link, quiz.id)
    await callback.bot.send_photo(callback.from_user.id,
                                  FSInputFile(f"qr_{quiz.id}.png", f"quizwings_qr_{quiz.id}.png"))


# Начало создания викторины
@router.callback_query(StatsQuizCallbackData.filter())
async def stats_quiz(callback: CallbackQuery, callback_data: StatsQuizCallbackData, state: FSMContext,
                     session: AsyncSession):
    db_query = await session.execute(select(Stat).filter_by(quiz_id=callback_data.quiz_id).order_by(Stat.id))
    stats = db_query.scalars().all()

    # Сортировка по последнему числу в stat.name
    stats_sorted = sorted(stats, key=lambda stat: int(stat.name.split()[-1].replace('</a>', '')))

    msg = ""
    for stat in stats_sorted:
        msg += f"{stat.name} правильных ответов: {stat.correct_count} из {stat.total_questions}\n"

    await callback.message.answer(msg, disable_web_page_preview=True)



# Начало создания викторины
@router.callback_query(F.data == "create_quiz")
async def create_quiz(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback.bot.send_sticker(callback.from_user.id, sticker=FSInputFile("sticker.tgs"))

    await callback.message.answer("Введите название викторины:")
    await state.set_state(QuizCreation.waiting_for_quiz_name)


@router.message(Command("create_quiz"))
async def create_quiz(message: Message, state: FSMContext, session: AsyncSession):
    await message.delete()
    await message.answer("Введите название викторины:")
    await state.set_state(QuizCreation.waiting_for_quiz_name)


# Получение названия викторины
@router.message(QuizCreation.waiting_for_quiz_name)
async def quiz_name_received(message: Message, state: FSMContext, session: AsyncSession):
    temporary_quiz_data[message.from_user.id] = {
        "name": message.text
    }
    await message.answer("Теперь давайте добавим первый вопрос. Введите текст вопроса:")
    await state.set_state(QuizCreation.waiting_for_question_text)


# Получение типа вопроса
@router.callback_query(QuizCreation.waiting_for_question_type, F.data.in_(["multiple_choice", "written"]))
async def question_type_received(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    question_type = callback.data
    temporary_quiz_data[callback.from_user.id]['current_question_type'] = question_type

    if question_type == "multiple_choice":
        await callback.message.answer("Введите варианты ответа через <b>;</b>")
        await state.set_state(QuizCreation.waiting_for_question_options)
    else:
        # Если письменный ответ, сразу переходим к правильному ответу
        await callback.message.answer("Введите правильный ответ:")
        await state.set_state(QuizCreation.waiting_for_correct_answer)


# Получение вариантов ответа (если множественный выбор)
@router.message(QuizCreation.waiting_for_question_options)
async def question_options_received(message: Message, state: FSMContext, session: AsyncSession):
    options = message.text.split(";")
    temporary_quiz_data[message.from_user.id]['current_question_options'] = [option.strip() for option in options]

    await message.answer("Укажите номер(а) правильных ответов через <b>;</b>")
    await state.set_state(QuizCreation.waiting_for_correct_answer)


# Получение правильного ответа
@router.message(QuizCreation.waiting_for_correct_answer)
async def correct_answer_received(message: Message, state: FSMContext, session: AsyncSession):
    question_type = temporary_quiz_data[message.from_user.id]['current_question_type']

    if question_type == "multiple_choice":
        correct_answers = message.text.split(";")

        temporary_quiz_data[message.from_user.id]['current_question_correct'] = [(int(answer.strip()) - 1) for answer in
                                                                                 correct_answers]
    else:
        temporary_quiz_data[message.from_user.id]['current_question_correct'] = message.text.strip()

    # Сохраняем вопрос в общий список вопросов викторины
    if "questions" not in temporary_quiz_data[message.from_user.id]:
        temporary_quiz_data[message.from_user.id]['questions'] = []

    # Добавляем текущий вопрос в список вопросов
    temporary_quiz_data[message.from_user.id]['questions'].append({
        "type": question_type,
        "question": temporary_quiz_data[message.from_user.id]['current_question_text'],
        "options": temporary_quiz_data[message.from_user.id].get('current_question_options', []),
        "correct": temporary_quiz_data[message.from_user.id]['current_question_correct']
    })

    builder = InlineKeyboardBuilder()
    builder.button(text="да", callback_data="add_new_question_yes")
    builder.button(text="нет", callback_data="add_new_question_no")
    builder.adjust(2)
    await message.answer("Вопрос добавлен! Хотите добавить ещё один вопрос?",
                         reply_markup=builder.as_markup())


# Завершение создания викторины
@router.callback_query(F.data == "add_new_question_no")
async def finish_quiz_creation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    result = await session.execute(select(func.max(Quiz.id)))
    last_id = result.scalar() or 0
    quiz = Quiz(
        id=last_id + 1,
        name=temporary_quiz_data[callback.from_user.id]['name'],
        user_id=callback.from_user.id,
        json=json.dumps({
            "questions": temporary_quiz_data[callback.from_user.id]['questions']
        })
    )
    await session.merge(quiz)
    await session.commit()

    await callback.message.answer("Ваша викторина успешно создана!")
    await state.clear()
    db_query = await session.execute(select(Quiz).filter_by(id=quiz.id, user_id=callback.from_user.id))
    quiz = db_query.scalar()
    await callback.message.answer(f"Викторина {quiz.id}: {quiz.name}",
                                  reply_markup=generate_my_quiz(quiz))
    temporary_quiz_data[callback.from_user.id].clear()


@router.callback_query(F.data == "add_new_question_yes")
async def add_another_question(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await callback.message.answer("Введите текст следующего вопроса:")
    await state.set_state(QuizCreation.waiting_for_question_text)


@router.message(QuizCreation.waiting_for_question_text)
async def question_text_received(message: Message, state: FSMContext, session: AsyncSession):
    temporary_quiz_data[message.from_user.id]['current_question_text'] = message.text

    # Предлагаем выбрать тип вопроса: множественный выбор или письменный ответ
    builder = InlineKeyboardBuilder()
    builder.button(text="с выбором ответа", callback_data="multiple_choice")
    builder.button(text="с письменным ответом", callback_data="written")
    builder.adjust(1)
    await message.answer("Выберите тип вопроса:", reply_markup=builder.as_markup())
    await state.set_state(QuizCreation.waiting_for_question_type)


# Сохранение имен пользователей
usernames = {}


# Начало участия в викторине
@router.message(F.text.startswith("/quiz "))
async def join_quiz(message: Message, state: FSMContext, session: AsyncSession):
    try:
        quiz_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("Неверный формат команды. Используйте /quiz <id_викторины>.")
        return

    # Проверяем наличие викторины в базе данных
    quiz = await session.get(Quiz, quiz_id)
    if not quiz:
        await message.answer(f"Викторина с ID {quiz_id} не найдена.")
        return

    # Проверяем, начата ли викторина
    if quiz.active:
        await message.answer("Викторина уже началась.")
        return

    # Сохраняем quiz_id в FSM
    await state.update_data(quiz_id=quiz_id)

    # Запрашиваем имя пользователя
    await message.answer("Пожалуйста, введите ваше имя и группу:")
    await state.set_state(QuizParticipation.waiting_for_name)


# Получение имени пользователя
@router.message(QuizParticipation.waiting_for_name)
async def name_received(message: Message, state: FSMContext, session: AsyncSession):
    if not message.text.split()[-1].isdigit():
        await message.answer("Пожалуйста, отправьте сообщение в формате 'Имя Фамилия Группа'. Например: Иван Иванов 5406")
        return

    # Извлекаем сохранённые данные состояния
    data = await state.get_data()
    quiz_id = data.get("quiz_id")

    # Сохраняем имя в словаре usernames
    usernames[message.from_user.id] = message.text

    quiz = await session.get(Quiz, quiz_id)
    if not quiz:
        await message.answer(f"Викторина с ID {quiz_id} не найдена.")
        return

    # Проверяем, начата ли викторина
    if quiz.active:
        await message.answer("Викторина уже началась.")
        return

    # Добавляем студента в список участников викторины
    if quiz_id not in current_quizzes:
        current_quizzes[quiz_id] = {"participants": {}}

    current_quizzes[quiz_id]["participants"][message.from_user.id] = {
        "current_question": 0,
        "correct_answers": 0
    }

    await message.answer(f"{message.text}, вы добавлены к викторине. Ожидание начала викторины от преподавателя.")
    await state.set_state(QuizParticipation.waiting_for_answer)


# Начало викторины преподавателем
@router.message(F.text.startswith("/quiz_start "))
async def start_quiz(message: Message, session: AsyncSession):
    try:
        quiz_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("Неверный формат команды. Используйте /quiz_start <id_викторины>.")
        return

    # Проверяем наличие викторины
    quiz = await session.get(Quiz, quiz_id)
    if not quiz:
        await message.answer(f"Викторина с ID {quiz_id} не найдена.")
        return

    if quiz.user_id != message.from_user.id:
        await message.answer(f"Это не Ваша викторина.")
        return

    # Устанавливаем статус викторины как активный
    quiz.active = True
    await session.commit()

    # Проверяем, есть ли участники
    if quiz_id not in current_quizzes or not current_quizzes[quiz_id]["participants"]:
        await message.answer("Нет участников для начала викторины.")
        return

    # Отправляем первый вопрос всем участникам
    quiz_data = json.loads(quiz.json)
    questions = quiz_data.get("questions", [])

    if not questions:
        await message.answer("Викторина не содержит вопросов.")
        return

    # Отправляем первый вопрос каждому участнику
    for user_id in current_quizzes[quiz_id]["participants"]:
        first_question = questions[0]
        await send_question(message.bot, user_id, first_question, 1)


@router.message(F.text.startswith("/quiz_stop "))
async def stop_quiz(message: Message, session: AsyncSession):
    try:
        quiz_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("Неверный формат команды. Используйте /quiz_start <id_викторины>.")
        return

    # Проверяем наличие викторины
    quiz = await session.get(Quiz, quiz_id)
    if not quiz:
        await message.answer(f"Викторина с ID {quiz_id} не найдена.")
        return

    if quiz.user_id != message.from_user.id:
        await message.answer(f"Это не Ваша викторина.")
        return
    # Устанавливаем статус викторины как активный
    quiz.active = False
    await session.commit()
    if quiz.id in current_quizzes:
        current_quizzes.pop(quiz.id)


async def send_question(bot: Bot, user_id: int, question_data: dict, question_number: int):
    """Отправляет вопрос, в зависимости от его типа"""
    question_type = question_data["type"]

    if question_type == "multiple_choice":
        # Отправляем опрос
        options = question_data["options"]
        await bot.send_poll(
            chat_id=user_id,
            allows_multiple_answers=True,
            question=question_data['question'],
            options=options,
            is_anonymous=False,
            type="regular",  # Устанавливаем тип опроса "викторина" для одного правильного ответа
        )
    elif question_type == "written":
        # Отправляем текстовый вопрос
        await bot.send_message(user_id, f"Вопрос {question_number}: {question_data['question']}")


# Обработка ответа пользователя
@router.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer, session: AsyncSession, state: FSMContext):
    user_id = poll_answer.user.id

    # Находим викторину, в которой участвует студент
    for quiz_id, quiz_data in current_quizzes.items():
        if user_id in quiz_data["participants"]:
            break
    else:
        return

    q = await session.get(Quiz, quiz_id)

    questions = json.loads(q.json)["questions"]
    current_question_index = quiz_data["participants"][user_id]["current_question"]
    current_question = questions[current_question_index]

    # Проверка ответа
    correct_option_ids = current_question["correct"]
    if set(poll_answer.option_ids) == set(correct_option_ids):
        quiz_data["participants"][user_id]["correct_answers"] += 1

        quiz = await session.get(Quiz, quiz_id)
        await poll_answer.bot.send_message(
            quiz.user_id,
            f"{get_clickable_name(poll_answer.user)} ответил правильно на вопрос {current_quizzes[quiz_id]['participants'][user_id]['current_question'] + 1}",
            disable_web_page_preview=True
        )
    else:
        quiz = await session.get(Quiz, quiz_id)
        await poll_answer.bot.send_message(
            quiz.user_id,
            f"{get_clickable_name(poll_answer.user)} ответил неправильно на вопрос {current_quizzes[quiz_id]['participants'][user_id]['current_question'] + 1}: {'; '.join([current_question['options'][i] for i in poll_answer.option_ids])}",
            disable_web_page_preview=True
        )

    # Переход к следующему вопросу
    current_quizzes[quiz_id]["participants"][user_id]["current_question"] += 1
    next_question_index = current_quizzes[quiz_id]["participants"][user_id]["current_question"]

    if next_question_index < len(questions):
        next_question = questions[next_question_index]
        await send_question(poll_answer.bot, user_id, next_question, next_question_index + 1)
    else:
        # Викторина завершена для пользователя
        correct_count = quiz_data["participants"][user_id]["correct_answers"]
        total_questions = len(questions)
        await poll_answer.bot.send_message(user_id,
                                           f"Викторина завершена! Вы ответили правильно на {correct_count} из {total_questions} вопросов.")
        quiz = await session.get(Quiz, quiz_id)
        await poll_answer.bot.send_message(
            quiz.user_id,
            f"{get_clickable_name(poll_answer.user)} закончил викторину. Правильных ответов: {correct_count} из {total_questions}.",
            disable_web_page_preview=True
        )
        await state.clear()

        result = await session.execute(select(func.max(Stat.id)))
        last_id = result.scalar() or 0
        stat = Stat(
            id=last_id + 1,
            user_id=poll_answer.user.id,
            name=get_clickable_name(poll_answer.user),
            quiz_id=quiz_id,
            correct_count=correct_count,
            total_questions=total_questions
        )
        await session.merge(stat)
        await session.commit()
        quiz_data["participants"].pop(user_id)
        # Можно добавить логику удаления пользователя из списка участников после завершения


# Обработка письменных ответов
@router.message(QuizParticipation.waiting_for_answer)
async def handle_written_answer(message: Message, session: AsyncSession, state: FSMContext):
    user_id = message.from_user.id

    # Находим викторину, в которой участвует студент
    for quiz_id, quiz_data in current_quizzes.items():
        if user_id in quiz_data["participants"]:
            break
    else:
        await message.answer("У вас нет активной викторины.")
        await state.clear()
        return

    questions = json.loads((await session.get(Quiz, quiz_id)).json)["questions"]
    current_question_index = quiz_data["participants"][user_id]["current_question"]
    current_question = questions[current_question_index]

    # Проверка правильности ответа
    correct_answer = current_question["correct"].strip().lower()
    user_answer = message.text.strip().lower()

    if user_answer == correct_answer:
        quiz_data["participants"][user_id]["correct_answers"] += 1
        await message.answer("Правильно!")
        quiz = await session.get(Quiz, quiz_id)
        await message.bot.send_message(
            quiz.user_id,
            f"{get_clickable_name(message.from_user)} ответил правильно на вопрос {current_quizzes[quiz_id]['participants'][user_id]['current_question'] + 1}",
            disable_web_page_preview=True
        )
    else:
        await message.answer(f"Неправильно. Правильный ответ: {current_question['correct']}")
        quiz = await session.get(Quiz, quiz_id)
        await message.bot.send_message(
            quiz.user_id,
            f"{get_clickable_name(message.from_user)} ответил неправильно на вопрос {current_quizzes[quiz_id]['participants'][user_id]['current_question'] + 1}: {message.text}",
            disable_web_page_preview=True
        )

    # Переход к следующему вопросу
    current_quizzes[quiz_id]["participants"][user_id]["current_question"] += 1
    next_question_index = current_quizzes[quiz_id]["participants"][user_id]["current_question"]

    if next_question_index < len(questions):
        next_question = questions[next_question_index]
        await send_question(message.bot, user_id, next_question, next_question_index + 1)
    else:
        # Викторина завершена для пользователя
        correct_count = quiz_data["participants"][user_id]["correct_answers"]
        total_questions = len(questions)
        await message.answer(
            f"Викторина завершена! Вы ответили правильно на {correct_count} из {total_questions} вопросов.")
        await state.clear()
        quiz = await session.get(Quiz, quiz_id)
        await message.bot.send_message(
            quiz.user_id,
            f"{get_clickable_name(message.from_user)} закончил викторину. Правильных ответов: {correct_count} из {total_questions}.",
            disable_web_page_preview=True
        )

        result = await session.execute(select(func.max(Stat.id)))
        last_id = result.scalar() or 0
        stat = Stat(
            id=last_id + 1,
            user_id=message.from_user.id,
            name=get_clickable_name(message.from_user),
            quiz_id=quiz_id,
            correct_count=correct_count,
            total_questions=total_questions
        )
        await session.merge(stat)
        await session.commit()
        quiz_data["participants"].pop(user_id)
