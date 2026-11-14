# Манометры · локальный модуль Python
## Быстрый запуск (Windows, Python 3.11 x64)
Запускайте команды из распакованной папки. Интернет нужен для установки библиотек. Веса уже в ov/. Вычисления выполняются на CPU.
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python gauge_reader.py examples/20190822_105.jpg examples/105.json --overlay result.jpg
```
JSON выводится в консоль. Координаты bbox заданы в пикселях исходного изображения в порядке left, top, right, bottom. Для второго кадра используйте 20190822_168.jpg и 168.json. На train_image.jpg с single.json ожидается manual_review из-за короткого видимого участка стрелки.
## Подключение к своему приложению
Поместите модуль и ov/ рядом, установите зависимости в окружение приложения. Импорт загружает обе модели один раз на процесс.
```python
from pathlib import Path
import json
from gauge_reader import read

profile = json.loads(Path("examples/105.json").read_text(encoding="utf-8-sig"))
for meter in read("examples/20190822_105.jpg", profile):
    if meter.get("status") == "read":
        print(meter["bbox"], meter["reading"], meter["unit"])
```
## Калибровка новой камеры
Профиль содержит список линейных шкал. Для одного прибора задайте x=[0,1]. Для нескольких задайте непересекающиеся интервалы по горизонтальной координате центра рамки, от 0 до 1. При смене расположения приборов обновите профиль. min и max — значения на концах шкалы, unit — обозначение единицы. start_deg — направление минимального деления в выровненных координатах, span_deg — размах шкалы по часовой стрелке. Ноль градусов направлен вправо, 90 градусов вниз. Проверьте калибровку на известных значениях.
## Что входит
PP-YOLOv2 определяет рамки. DeepLabV3+ выделяет стрелку и штрихи. Код вычисляет значение по углу и профилю. score характеризует обнаружение прибора. При отсутствии обнаружений возвращается пустой список. manual_review означает, что численное значение использовать нельзя. Модуль оценивает давление по фотографии; сверка со SCADA и OCR в этот вариант не входят.
В examples лежат оригиналы и результаты с разметкой, в reference — исходный эксперимент и сохранённые результаты для сравнения. Основная точка входа — gauge_reader.py.
Источники: PaddleX Meter Reader (https://github.com/PaddlePaddle/PaddleX/tree/release/2.1/examples/meter_reader), веса из OpenVINO Notebooks (https://github.com/openvinotoolkit/openvino_notebooks/tree/latest/notebooks/meter-reader), крупный план ALLWEILER из GaugereaderProject (https://github.com/Guydada/GaugereaderProject).
