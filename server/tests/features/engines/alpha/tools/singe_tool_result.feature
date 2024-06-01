Feature: Single Tool Result 
    Scenario: Drinks availability tool is bieng called
        Given the alpha engine
        And an agent
        And an empty session
        And guidelines
        And tools
        And check_drinks_in_stock guideline
        And get_available_drinks tool
        And connection between get_available_drinks and check_drinks_in_stock
        And an empty session
        And a server message of You are a salesperson of pizza place
        And a user message of Hey, Can I order large pepperoni pizza with Sprite?
        When processing is triggered
        Then a single tool event is produced
        And a drinks-available-in-stock tool event is produced in tool event number 1

    Scenario: Toppings availability tool is bieng called
        Given the alpha engine
        And an agent
        And an empty session
        And guidelines
        And tools
        And check_toppings_in_stock guideline
        And get_available_toppings tool
        And connection between get_available_toppings and check_toppings_in_stock
        And an empty session
        And a server message of You are a salesperson of pizza place
        And a user message of Hey, Can I order large pepperoni pizza with Sprite?
        When processing is triggered
        Then a single tool event is produced
        And a toppings-available-in-stock tool event is produced in tool event number 1