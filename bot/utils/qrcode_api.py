import io
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
from PIL import Image, ImageDraw


def add_rounded_corners(image, radius):
    # Создаем маску с закругленными углами
    mask = Image.new('L', image.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, image.size[0], image.size[1]], radius=radius, fill=255)

    # Применяем маску к изображению
    rounded_image = image.copy()
    rounded_image.putalpha(mask)

    return rounded_image


def generate_qr_code(data, id):
    qr = qrcode.QRCode(
        version=1,  # Версия QR-кода
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # Высокая коррекция ошибок
        box_size=20,
        border=1,  # Толщина границы QR-кода
    )

    # Добавляем данные (ссылку) в QR-код
    qr.add_data(data)
    qr.make(fit=True)

    # Генерируем QR-код с голубым цветом и закругленными модулями
    img_qr = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),  # Закругленные модули
        color_mask=SolidFillColorMask(back_color=(255, 255, 255), front_color=(89, 173, 209))  # Голубой цвет
    )

    # Открываем логотип
    logo = Image.open('logo.png')  # Замените 'logo.jpg' на ваш файл логотипа
    if logo.mode != 'RGBA':
        logo = logo.convert('RGBA')
    # Изменяем размер логотипа под QR-код (логотип займет примерно 1/4 часть QR-кода)
    qr_size = img_qr.size
    logo_size = qr_size[0] // 4
    logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

    # Вычисляем позицию для логотипа (центр QR-кода)
    logo_position = (
        (qr_size[0] - logo_size) // 2,
        (qr_size[1] - logo_size) // 2
    )

    # Вставляем логотип в центр QR-кода
    img_qr.paste(logo, logo_position, mask=logo)  # Вставляем логотип с использованием маски для прозрачности

    # Сохраняем итоговое изображение
    img_qr.save(f'qr_{id}.png')
    return img_qr


def create_qr_code_png(data: str, logo_path: str = None):
    # Генерируем QR-код
    qr_image = generate_qr_code(data, box_size=20, border=1)

    # Добавляем закругленные углы к QR-коду
    radius = 20  # Радиус закругления углов
    qr_image = add_rounded_corners(qr_image, radius)

    if logo_path:
        # Открываем логотип
        logo_image = Image.open(logo_path).convert("RGBA")

        # Размер логотипа относительно QR-кода
        logo_size = int(min(qr_image.size[0], qr_image.size[1]) / 4)
        logo_image = logo_image.resize((logo_size, logo_size), Image.LANCZOS)

        # Добавляем логотип в центр QR-кода
        pos = ((qr_image.size[0] - logo_image.size[0]) // 2, (qr_image.size[1] - logo_image.size[1]) // 2)
        qr_image.paste(logo_image, pos, mask=logo_image)

    # Сохраняем QR-код с логотипом в буфер BytesIO
    output = io.BytesIO()
    qr_image.save(output, format='PNG')

    # Перемещаемся в начало буфера
    output.seek(0)

    # Возвращаем объект BytesIO с PNG изображением
    return output
