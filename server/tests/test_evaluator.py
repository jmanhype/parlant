async def test_that_a_new_evaluation_starts_with_a_pending_status() -> None: ...
async def test_that_an_evaluation_completes_when_all_items_have_an_invoice() -> None: ...
async def test_that_an_evaluation_of_a_coherent_guideline_completes_with_an_approved_invoice() -> (
    None
): ...


async def test_that_an_evaluation_of_an_incoherent_guideline_completes_with_an_unapproved_invoice() -> (
    None
): ...


async def test_that_an_evaluation_of_multiple_items_completes_with_an_invoice_for_each() -> (
    None
): ...


async def test_that_an_evaluation_that_failed_due_to_invalid_data_contains_error_details() -> (
    None
): ...


async def test_that_an_evaluation_that_failed_due_to_failed_items_contains_its_error_details_as_well_as_the_error_details_of_failed_items() -> (
    None
): ...
