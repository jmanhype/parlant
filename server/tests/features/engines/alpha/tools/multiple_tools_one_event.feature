Feature: Multiple tools in one event
    Scenario: Product availability tools called twice for drinks and toppings
        Given the alpha engine
        And an agent
        And an empty session
        And guidelines
        And tools
        And check_toppings_or_drinks_in_stock guideline
        And get_available_product_by_type tool
        And connection between get_available_product_by_type and check_toppings_or_drinks_in_stock
        And an empty session
        And a server message of You are a salesperson of pizza place
        And a user message of Hey, Can I order large pepperoni pizza with Sprite?
        When processing is triggered
        Then a single tool event is produced
        And a product availability for drinks tool event is produced in tool event number 1
        And a product availability for toppings tool event is produced in tool event number 1

    Scenario: Add tools called twice
        Given the alpha engine
        And an agent
        And an empty session
        And guidelines
        And tools
        And calculate_sum guideline
        And add tool
        And connection between add and calculate_sum
        And an empty session
        And a user message of What is 8+2 and 4+6?
        When processing is triggered
        Then a single tool event is produced
        And an add tool event is produced with 8, 2 numbers in tool event number 1
        And an add tool event is produced with 4, 6 numbers in tool event number 1

    Scenario: Drinks and toppings tools called from different guidelines
        Given the alpha engine
        And an agent
        And an empty session
        And guidelines
        And tools
        And check_drinks_or_toppings_in_stock guideline
        And get_available_drinks tool
        And get_available_toppings tool
        And connection between get_available_drinks and check_drinks_or_toppings_in_stock
        And connection between get_available_toppings and check_drinks_or_toppings_in_stock
        And an empty session
        And a server message of You are a salesperson of pizza place
        And a user message of Hey, Can I order large pepperoni pizza with Sprite?
        When processing is triggered
        Then a single tool event is produced
        And a toppings-available-in-stock tool event is produced in tool event number 1
        And a drinks-available-in-stock tool event is produced in tool event number 1

    Scenario: Drinks and toppings tools called from same guideline
        Given the alpha engine
        And an agent
        And an empty session
        And guidelines
        And tools
        And check_drinks_in_stock guideline
        And check_toppings_in_stock guideline
        And get_available_drinks tool
        And get_available_toppings tool
        And connection between get_available_drinks and check_drinks_in_stock
        And connection between get_available_toppings and check_toppings_in_stock
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
        And guidelines
        And tools
        And calculate_addition_or_multiplication guideline
        And add tool
        And multiply tool
        And connection between add and calculate_addition_or_multiplication
        And connection between multiply and calculate_addition_or_multiplication
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
        And guidelines
        And tools
        And calculate_addition_or_multiplication guideline
        And add tool
        And multiply tool
        And connection between add and calculate_addition_or_multiplication
        And connection between multiply and calculate_addition_or_multiplication
        And an empty session
        And a user message of what is 8+2 and 4*6? also, 9+5 and 10+2 and 3*5
        When processing is triggered
        Then a single tool event is produced
        And an add tool event is produced with 8, 2 numbers in tool event number 1
        And a multiply tool event is produced with 4, 6 numbers in tool event number 1
        And an add tool event is produced with 10, 2 numbers in tool event number 1
        And a multiply tool event is produced with 3, 5 numbers in tool event number 1