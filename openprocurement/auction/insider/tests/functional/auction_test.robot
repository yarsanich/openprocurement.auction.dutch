*** Settings ***

Documentation  A test suite with a tests for insider tender auction.
Suite setup       Отримати вхідні дані
Suite teardown    Close all browsers
Resource       resource.robot

*** Test Cases ***
Перевірка логіну
    Долучитись до аукціону 1 учасником
    Долучитись до аукціону 2 учасником

Очікування початку голландської частини аукціону
    Дочекатись паузи до Голландського етапу
    Перевірити інформацію про тендер
    Дочекатись завершення паузи перед Голландського етапом

Голландський аукціон
    Долучитись до аукціону 3 учасником
    Зробити заявку
    Долучитись до аукціону 4 учасником

Очікування початку Sealed Bid етапу
    Дочекатись паузи до Sealed Bid етапу
    Дочекатись завершення паузи перед Sealed Bid етапом

Проведення Sealed Bid частини аукціону
    Долучитись до аукціону глядачем
    Долучитись до аукціону 5 учасником
    Спробувати зробити надто низьку ставку
    Переключитись на 1 учасника
    Зробити ставку
    Відредагувати ставку
    Відмінити ставку
    Переключитись на 2 учасника
    Зробити ставку
    Переключитись на 4 учасника
    Зробити ставку

Очікування початку Best Bid етапу
    Дочекатись паузи до Best Bid етапу
    Дочекатись завершення паузи перед Best Bid етапом

Проведення Bestbid частини аукціону
    Переключитись на 3 учасника
    Спробувати зробити невалідну ставку переможцем голландської частини
    Підвищити пропозицію переможцем голландської частини

Завершення аукціону
    Дочекатись завершення аукціону