Feature: Single Tool Event
    Scenario Outline: Single tool is being called once
        Given the alpha engine
        And an agent
        And an empty session
        And a diverse selection of guidelines
        And a diverse selection of tools
        And <guideline_name> guideline
        And <tool_name> tool
        And an association between <guideline_name> and <tool_name>
        And an empty session
        And a server message of You are a salesperson of pizza place
        And a user message of Hey, Can I order large pepperoni pizza with Sprite?
        When processing is triggered
        Then a single tool event is produced
        And a <tool_event_name> tool event is produced in tool event number 1
        Examples:
            | guideline_name          | tool_name              | tool_event_name             |
            | check_drinks_in_stock   | get_available_drinks   | drinks-available-in-stock   |
            | check_toppings_in_stock | get_available_toppings | toppings-available-in-stock |

    Scenario: Single tool is being called multiple times
        Given the alpha engine
        And an agent
        And an empty session
        And a diverse selection of guidelines
        And a diverse selection of tools
        And check_toppings_or_drinks_in_stock guideline
        And get_available_product_by_type tool
        And an association between check_toppings_or_drinks_in_stock and get_available_product_by_type
        And an empty session
        And a server message of You are a salesperson of pizza place
        And a user message of Hey, Can I order large pepperoni pizza with Sprite?
        When processing is triggered
        Then a single tool event is produced
        And a tool event for product availability of drinks is generated at tool event number 1
        And a tool event for product availability of toppings is generated at tool event number 1

    Scenario: Add tools called twice
        Given the alpha engine
        And an agent
        And an empty session
        And a diverse selection of guidelines
        And a diverse selection of tools
        And calculate_sum guideline
        And add tool
        And an association between calculate_sum and add
        And an empty session
        And a user message of What is 8+2 and 4+6?
        When processing is triggered
        Then a single tool event is produced
        And an add tool event is produced with 8, 2 numbers in tool event number 1
        And an add tool event is produced with 4, 6 numbers in tool event number 1

    Scenario: Drinks and toppings tools called from same guideline
        Given the alpha engine
        And an agent
        And an empty session
        And a diverse selection of guidelines
        And a diverse selection of tools
        And check_drinks_or_toppings_in_stock guideline
        And get_available_drinks tool
        And get_available_toppings tool
        And an association between check_drinks_or_toppings_in_stock and get_available_drinks
        And an association between check_drinks_in_stock and get_available_toppings
        And an empty session
        And a server message of You are a salesperson of pizza place
        And a user message of Hey, Can I order large pepperoni pizza with Sprite?
        When processing is triggered
        Then a single tool event is produced
        And a toppings-available-in-stock tool event is produced in tool event number 1
        And a drinks-available-in-stock tool event is produced in tool event number 1

    Scenario: Drinks and toppings tools called from different guidelines
        Given the alpha engine
        And an agent
        And an empty session
        And a diverse selection of guidelines
        And a diverse selection of tools
        And check_drinks_in_stock guideline
        And check_toppings_in_stock guideline
        And get_available_drinks tool
        And get_available_toppings tool
        And an association between check_drinks_in_stock and get_available_drinks
        And an association between check_toppings_in_stock and get_available_toppings
        And an empty session
        And a server message of You are a salesperson of pizza place
        And a user message of Hey, Can I order large pepperoni pizza with Sprite?
        When processing is triggered
        Then a single tool event is produced
        And a toppings-available-in-stock tool event is produced in tool event number 1

    Scenario: Add and multiply tools called once each
        Given the alpha engine
        And an agent
        And an empty session
        And a diverse selection of guidelines
        And a diverse selection of tools
        And calculate_addition_or_multiplication guideline
        And add tool
        And multiply tool
        And an association between calculate_addition_or_multiplication and add
        And an association between calculate_addition_or_multiplication and multiply
        And an empty session
        And a user message of what is 8+2 and 4*6?
        When processing is triggered
        Then a single tool event is produced
        And an add tool event is produced with 8, 2 numbers in tool event number 1
        And a multiply tool event is produced with 4, 6 numbers in tool event number 1

    Scenario: Add and multiply tools called multiple times each
        Given the alpha engine
        And an agent
        And an empty session
        And a diverse selection of guidelines
        And a diverse selection of tools
        And calculate_addition_or_multiplication guideline
        And add tool
        And multiply tool
        And an association between calculate_addition_or_multiplication and add
        And an association between calculate_addition_or_multiplication and multiply
        And an empty session
        And a user message of what is 8+2 and 4*6? also, 9+5 and 10+2 and 3*5
        When processing is triggered
        Then a single tool event is produced
        And an add tool event is produced with 8, 2 numbers in tool event number 1
        And a multiply tool event is produced with 4, 6 numbers in tool event number 1
        And an add tool event is produced with 10, 2 numbers in tool event number 1
        And a multiply tool event is produced with 3, 5 numbers in tool event number 1

    Scenario: Tool called again by context after user response
        Given the alpha engine
        And an agent
        And an empty session
        And a diverse selection of guidelines
        And a diverse selection of tools
        And retrieve_account_information guideline
        And get_account_balance tool
        And an association between retrieve_account_information and get_account_balance
        And an empty session
        And a user message of What is the balance of Larry David account?
        And a tool event with data of [{ "tool_calls": { "tool_name": "get_account_balance", "parameters": { "account_name": "Larry David"}, "result": 450000000}}]
        And a server message of Larry David currently has 450 million dollars.
        And a user message of And what about now?
        When processing is triggered
        Then a single tool event is produced
        And a get balance account tool event is produced for the Larry David account in tool event number 1
