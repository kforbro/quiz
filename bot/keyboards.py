from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.common import SelectQuizCallbackData, InviteQuizCallbackData, StopQuizCallbackData, \
    StartQuizCallbackData, StatsQuizCallbackData


def generate_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="новая викторина", callback_data="create_quiz")
    builder.button(text="мои викторины", callback_data="my_quizzes")
    return builder.adjust(2).as_markup()


def generate_my_quizzes(quizzes) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for quiz in quizzes:
        builder.button(text=f"{quiz.name}", callback_data=SelectQuizCallbackData(quiz_id=quiz.id))

    return builder.adjust(1).as_markup()


def generate_my_quiz(quiz) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=f"начать", callback_data=StartQuizCallbackData(quiz_id=quiz.id))
    builder.button(text=f"стоп", callback_data=StopQuizCallbackData(quiz_id=quiz.id))
    builder.button(text=f"QR-code", callback_data=InviteQuizCallbackData(quiz_id=quiz.id))
    builder.button(text=f"статистика", callback_data=StatsQuizCallbackData(quiz_id=quiz.id))

    return builder.adjust(2).as_markup()
