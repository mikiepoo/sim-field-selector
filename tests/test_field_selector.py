import unittest

from field_selector import RosterDriver, select_field


ROSTER = [
    RosterDriver("1", "Locked Driver", "charter"),
    RosterDriver("2", "OC Fast", "open-charter"),
    RosterDriver("3", "OC Slow", "open-charter"),
    RosterDriver("4", "Open Fast", "open"),
    RosterDriver("5", "Open Slow", "open"),
]


class FieldSelectorTests(unittest.TestCase):
    def test_applies_all_three_selection_stages(self):
        result = select_field(
            ["Open Fast", "OC Fast", "Open Slow", "OC Slow", "Locked Driver"],
            ROSTER,
            open_charter_spots=1,
            open_spots=1,
        )
        by_name = {row["name"]: row for row in result["drivers"]}
        self.assertEqual(by_name["Locked Driver"]["reason"], "Charter locked")
        self.assertEqual(by_name["OC Fast"]["reason"], "Open-Charter position")
        self.assertEqual(by_name["Open Fast"]["reason"], "Open position")
        self.assertEqual(by_name["OC Slow"]["result"], "DNQ")

    def test_open_charter_loser_can_take_open_position(self):
        result = select_field(["OC Fast", "OC Slow", "Open Fast"], ROSTER, 1, 1)
        self.assertEqual(result["drivers"][1]["reason"], "Open position")
        self.assertEqual(result["drivers"][2]["result"], "DNQ")
        self.assertEqual(result["summary"]["open_charter_in"], 2)
        self.assertEqual(result["summary"]["open_charter_via_final_pool"], 1)
        self.assertEqual(result["summary"]["open_in"], 0)

    def test_absent_charter_is_not_added_to_field(self):
        result = select_field(["OC Fast"], ROSTER, 1, 0, field_size=2)
        self.assertNotIn("Locked Driver", {row["name"] for row in result["drivers"]})
        self.assertEqual(result["summary"]["entered"], 1)
        self.assertEqual(result["summary"]["unfilled_spots"], 1)

    def test_rejects_configuration_over_field_size(self):
        with self.assertRaisesRegex(Exception, "exceeds the 2-driver field"):
            select_field(["Locked Driver", "OC Fast"], ROSTER, 1, 1, field_size=2)

    def test_absent_charter_vacancy_expands_final_pool(self):
        result = select_field(["OC Fast", "Open Fast", "OC Slow"], ROSTER, 1, 1, field_size=3)
        self.assertEqual(result["summary"]["open_charter_selected"], 1)
        self.assertEqual(result["summary"]["open_selected"], 2)
        self.assertEqual(result["summary"]["added_vacancy_spots"], 1)
        self.assertEqual(result["summary"]["missing_charters"], 1)
        self.assertEqual(result["summary"]["in_field"], 3)

    def test_unmatched_and_duplicate_are_not_guessed(self):
        result = select_field(["OC Fast", "OC Fast", "OC Fst"], ROSTER, 1, 1)
        self.assertEqual(result["summary"]["entered"], 1)
        self.assertEqual(result["summary"]["unmatched"], 2)

if __name__ == "__main__":
    unittest.main()
