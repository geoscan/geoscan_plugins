# Плагины для Agisoft Metashape

Данные плагины предназначены для расширения функциональных возможностей [Agisoft Metashape](https://www.agisoft.com/). Плагины представляют собой отдельные программы с собственным интерфейсом, которые запускаются внутри Agisoft Metashape.

Узнать подробнее о возможностях каждого из плагинов можно ниже, перейдя по ссылке с интересующим плагином.

Если у вас возникли проблемы по работе с плагинами, либо появились замечания и предложения, мы будем рады, если вы оставите соответствующий **issue** [здесь](https://github.com/geoscan/geoscan_plugins/issues). Pull requests приветствуются :wink:.

## Содержание
- [Системные требования](#системные-требования)
- [Лицензия](#лицензия)
- [Установка](#установка)
- [Список плагинов](#список-плагинов)
- [Автоматическое обновление](#автоматическое-обновление)
- [Сбор информации об ошибках](#сбор-информации-об-ошибках)
- [Удаление](#удаление)
- [Примечание](#примечание)

## Системные требования
- ОС **Windows**
- **Agisoft Metashape** версии **1.7** и выше. 

_Последняя проверка работоспособности плагинов блока Фигуры проводилась в Agisoft Metashape 1.7.6.13779 и 1.8.1.13915_

_Последняя проверка работоспособности плагинов остальных блоков производилась в Agisoft Metashape 1.7.3.12473_

## Лицензия
Данное программное обеспечение имеет лицензию GNU General Public License version 3.
Подробнее - в файле [LICENSE](https://github.com/geoscan/geoscan_plugins/blob/main/LICENSE).

## Установка
Для установки вы можете воспользоваться одним из способов:

***Способ 1***. [Скачать](https://github.com/geoscan/geoscan_plugins/releases/latest/download/geoscan_plugins_installer.exe) установщик плагинов и установить. 

***Способ 2***. Скачать исходный код из репозитория и разместить в папке _%localappdata%\Agisoft\Metashape Pro\scripts_ (если папки scripts не существует, то необходимо ее создать). 

_После установки, в обоих случаях, при первом запуске Agisoft Metashape требуется иметь подключение к сети Интернет для установки необходимых зависимостей._

Если у вас возникли проблемы во время первого запуска после установки плагинов 
(не появилась вкладка плагинов, неполный список плагинов, ошибки импорта зависимостей в консоли программы и др.),
попробуйте переустановить плагины при помощи [установщика](https://github.com/geoscan/geoscan_plugins/releases/latest/download/geoscan_plugins_installer_offline.exe), 
который устанавливает все необходимые зависимости без подключения к Интернету.

## Список плагинов
### Блок **ГНСС**
1. [Обработка геодезических измерений](https://github.com/geoscan/geoscan_plugins/blob/main/gnss_post_processing#readme)
2. [Соединить Magnet XML файлы](https://github.com/geoscan/geoscan_plugins/blob/main/gnss_processing#readme)
### Блок **Камеры**
3. [Коррекция гаммы изображений](https://github.com/geoscan/geoscan_plugins/tree/main/auto_gamma_correction#readme)
4. [Вертикальное выравнивание](https://github.com/geoscan/geoscan_plugins/blob/main/fast_layout#readme)
5. [Оценка качества исходных снимков](https://github.com/geoscan/geoscan_plugins/blob/main/quality_estimator#readme)
6. [Микшер каналов изображений](https://github.com/geoscan/geoscan_plugins/blob/main/image_channel_mixer#readme)
7. [Построить маски по контурам](https://github.com/geoscan/geoscan_plugins/blob/main/contour_tools#readme)
8. [Удалить дубликаты изображений](https://github.com/geoscan/geoscan_plugins/blob/main/remove_image_duplicates#readme)
### Блок **Фигуры**
9. [Построить буферную зону](https://github.com/geoscan/geoscan_plugins/blob/main/buffer_by_markers#readme)
10. [Экспортировать по фигурам](https://github.com/geoscan/geoscan_plugins/blob/main/export_by_shapes#readme)
11. [Построить номенклатурную разграфку](https://github.com/geoscan/geoscan_plugins/blob/main/shape_worker#построить-номенклатурную-разграфку)
12. [Задать высоту выбранной фигуре](https://github.com/geoscan/geoscan_plugins/blob/main/set_altitudes_for_shape#readme)
13. [Построить регулярную сетку](https://github.com/geoscan/geoscan_plugins/tree/main/shape_worker#построить-регулярную-сетку)
### Блок **Модель**
14. [Экспорт/Импорт модели по маркеру](https://github.com/geoscan/geoscan_plugins/blob/main/expimp_by_marker#readme)
15. [Построить стены](https://github.com/geoscan/geoscan_plugins/blob/main/mesh_creator#readme)
### Блок **Другое**
16. [Задать регион](https://github.com/geoscan/geoscan_plugins/blob/main/chunk_region_setter#readme)
17. [Добавить пользовательские системы координат](https://github.com/geoscan/geoscan_plugins/blob/main/crs_uploader#readme)
18. [Создание MapInfo TAB-файлов для ортофотопланов](https://github.com/geoscan/geoscan_plugins/blob/main/tab_meta_creator#readme)

## Автоматическое обновление
Исходный код плагинов может быть автоматически обновлен на компьютерах пользователей. 
Автоматические обновления могут быть отключены в настройках плагинов.

## Сбор информации об ошибках
По умолчанию, в плагинах включена опция сбора логов о некоторых неожиданных ошибках, которые отправляются разработчикам. 
Сбор логов может быть отключен в настройках.

## Удаление

Для полного удаления плагинов необходимо удалить следующие папки:
- _%localappdata%\Agisoft\Metashape Pro\scripts_
- _%localappdata%\Agisoft\Metashape Pro\site-packages-py38_
- _%localappdata%\Agisoft\Metashape Pro\resources_

## Примечание

Изначально, данные плагины разрабатывались программистами и ГИС-специалистами компании Геоскан для автоматизации и решения своих ежедневных задач, связанных с обработкой аэрофотосъемочных данных. 

Мы выкладываем исходный код данных программ в состоянии **как есть** и надеемся, что данные плагины и их исходный код помогут вам в решении своих собственных задач при помощи Agisoft Metashape.
