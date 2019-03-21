*** Settings ***
Library        Selenium2Library
Library        Selenium2Screenshots
Library        DebugLibrary
Resource       users_keywords.robot
Library        openprocurement.auction.insider.tests.functional.service_keywords

*** Variables ***
${USERS}
${USERS_ids}
${BROWSER}       chrome

*** Keywords ***
Отримати вхідні дані
  ${TENDER}=  prepare_tender_data
  Set Global Variable  ${TENDER}
  ${USERS}=  prepare_users_data  ${TENDER}
  ${USERS_ids}=  Convert to List  ${USERS}
  Set Global Variable  ${USERS}
  Set Global Variable  ${USERS_ids}
  Log  ${USERS_ids}
  :FOR  ${index}  IN RANGE  0  3
  \  Log  ${USERS['${USERS_ids[${index}]}']['login_url']}  WARN


Долучитись до аукціону ${user_index} учасником
  ${user_index}=  Evaluate  ${user_index}-1
  Підготувати клієнт для ${user_index} користувача
  Залогуватись ${user_index} користувачем
  Перевірити інформацію з меню

Долучитись до аукціону глядачем
  Open Browser  http://localhost:8090/insider-auctions/11111111111111111111111111111111  ${BROWSER}
  Set Window Position  ${0}  ${0}
  Set Window Size  ${300}  ${1200}
  Wait Until Page Contains  Ви спостерігач і не можете робити ставки
  Run Keyword And Expect Error  *  Зробити ставку

Перевірити інформацію з меню
  Wait Until Page Contains Element  id=menu_button  10 s
  Click Element  id=menu_button
  Wait Until Page Contains  Browser ID
  Highlight Elements With Text On Time  Browser ID
  Wait Until Page Contains   Session ID
  Highlight Elements With Text On Time  Session ID
  Capture Page Screenshot
  Press Key  xpath=/html/body/div/div[1]/div/div[1]/div[1]/button     \\27
  sleep  1s

Дочекатись паузи до ${stage_name} етапу
  Wait Until Page Contains  ${stage_name}  10 min

Дочекатись завершення паузи перед ${stage_name} етапом
  Wait Until Page Does Not Contain  → ${stage_name}  10 min

Дочекатись завершення аукціону
  Wait Until Page Contains  Аукціон завершився  10 min

Перевірити інформацію про тендер
  Page Should Contain  ${TENDER['title']}                    # tender title
  Page Should Contain  ${TENDER['procuringEntity']['name']}  # tender procuringEntity name

Відображення повідомлення для переможця голландської частини
  Wait Until Page Contains  Щоб подати ставку, будь ласка, дочекайтесь етапу подання відкритих цінових пропозицій

Відображення повідомлення для sealedbid учасника
  Wait Until Page Contains  Ви не маєте змоги робити ставки на етапі подання відкритих цінових пропозицій

Перевірити оголошення результатів
  Element Should Contain   id=stage-announcement-1  МТС Україна
  Element Should Contain   id=stage-announcement-2  ЛАЙФСЕЛЛ
  Element Should Contain   id=stage-announcement-3  КИЇВСТАР