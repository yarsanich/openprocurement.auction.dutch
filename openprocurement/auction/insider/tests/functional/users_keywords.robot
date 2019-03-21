*** Variables ***
${dutch_amount}  xpath=(//div[@id='stage-sealedbid-dutch-winner']//span[@class='label-price ng-binding'])
${sealedbid_amount}  xpath=(//div[contains(concat(' ', normalize-space(@class), ' '), ' sealedbid-winner ')]//span[@class='label-price ng-binding'])

*** Keywords ***
Підготувати клієнт для ${user_index} користувача
    ${user_id}=  Get Variable Value  ${USERS_ids[${user_index}]}
    Open Browser  https://prozorro.sale/  ${BROWSER}  ${user_id}
    Set Window Position  @{USERS['${user_id}']['position']}
    Set Window Size  @{USERS['${user_id}']['size']}

Залогуватись ${user_index} користувачем
    ${user_id}=  Get Variable Value  ${USERS_ids[${user_index}]}
    Go to  ${USERS['${user_id}']['login_url']}
    Wait Until Page Contains  Дякуємо за використання електронної торгової системи ProZorro.Продажі
    Highlight Elements With Text On Time  Так
    Capture Page Screenshot
    Click Element  confirm

Переключитись на ${user_index} учасника
    ${user_index}=  Evaluate  ${user_index}-1
    ${user_id}=  Get Variable Value  ${USERS_ids[${user_index}]}
    Switch Browser  ${user_id}
    ${CURRENT_USER}=  set variable  ${user_id}
    Set Global Variable  ${CURRENT_USER}

Зробити ставку під час ducth частини
    Highlight Elements With Text On Time  Зробити ставку
    Click Element  id=place-bid-button
    Wait Until Page Contains  Ви

Зробити ставку
    Поставити ставку  1  Ставку прийнято  ${dutch_amount}

Спробувати зробити надто низьку ставку
    Поставити ставку  -1  Значення пропозиції не може бути меншою чи рівною поточній сумі  ${dutch_amount}

Підвищити пропозицію переможцем голландської частини
    Поставити ставку  ${step_amount}  Ставку прийнято  ${sealedbid_amount}

Спробувати зробити невалідну ставку переможцем голландської частини
    ${step_amount}=  calculate_step_amount  ${TENDER}
    Set Global Variable  ${step_amount}
    ${invalid_amount}=  Evaluate  ${step_amount}-1
    Поставити ставку  ${invalid_amount}  Ваша ставка повинна перевищувати ставку переможця попередньої стадії як мінімум на 1 крок (1% від початкової вартості)  ${sealedbid_amount}

Поставити ставку
    [Arguments]  ${step}  ${msg}  ${locator}
    Wait Until Page Contains Element  ${locator}
    ${last_amount}=  Get Text  ${locator}
    Highlight Elements With Text On Time  ${last_amount}
    ${last_amount}=  convert_amount_to_number  ${last_amount}
    ${amount}=  Evaluate  ${last_amount}+${step}
    ${input_amount}=  Convert To String  ${amount}
    Input Text  id=bid-amount-input  ${input_amount}
    sleep  1s
    Capture Page Screenshot
    Highlight Elements With Text On Time  Зробити ставку
    Click Element  id=place-bid-button
    Wait Until Page Contains  ${msg}  10s
    Capture Page Screenshot

Відредагувати ставку
    Wait Until Page Contains Element  id=edit-bid-button
    Highlight Element  id=edit-bid-button
    Click Element  id=edit-bid-button
    Input Text  id=bid-amount-input  1
    Capture Page Screenshot
    Click Element  id=clear-bid-button
    Capture Page Screenshot
    Поставити ставку  1  Ставку прийнято  ${dutch_amount}
    Capture Page Screenshot

Відмінити ставку
    Highlight Elements With Text On Time  Відмінити ставку
    Click Element  id=cancel-bid-button
    Wait Until Page Contains  Ставку відмінено  10s
    Highlight Elements With Text On Time  Ставку відмінено
    Capture Page Screenshot
