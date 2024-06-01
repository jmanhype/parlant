Feature: Multiple Tool Events
    Scenario: Guideline is retrieved after user responded, and the tool is called again.
        Given the alpha engine
        Then the following tool events got produced: 
        """
        {
            "tool_id_1": 5,
            "tool_id_2": 3
        }
        """