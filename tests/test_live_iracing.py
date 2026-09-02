import unittest

from live_iracing import LiveIRacingReader


class FakeSdk:
    def __init__(self):
        self.is_initialized = False
        self.is_connected = True
        self.data = {
            "DriverInfo": {"Drivers": [
                {"CarIdx": 0, "UserID": 1109711, "UserName": "Terrence Murphy", "CarNumber": "5", "IsSpectator": 0, "CarIsPaceCar": 0},
                {"CarIdx": 1, "UserID": 574792, "UserName": "James Coffman", "CarNumber": "01", "IsSpectator": 0, "CarIsPaceCar": 0},
                {"CarIdx": 2, "UserID": 0, "UserName": "Pace Car", "CarNumber": "0", "IsSpectator": 0, "CarIsPaceCar": 1},
            ]},
            "SessionNum": -2,
            "SessionInfo": {"Sessions": [{"SessionNum": -2, "SessionName": "QUALIFY", "ResultsPositions": []}]},
            "QualifyResultsInfo": {"Results": [
                {"Position": 1, "CarIdx": 0, "FastestTime": 30.1},
                {"Position": 0, "CarIdx": 1, "FastestTime": 29.9},
            ]},
            "SessionState": 4,
            "SessionTime": 91.5,
            "SessionTimeRemain": 508.5,
            "WeekendInfo": {
                "SubSessionID": 88235141,
                "TrackID": 123,
                "TrackDisplayName": "Charlotte Motor Speedway",
                "TrackConfigName": "Oval",
            },
        }

    def startup(self):
        self.is_initialized = True
        return True

    def shutdown(self):
        self.is_initialized = False

    def freeze_var_buffer_latest(self):
        return None

    def __getitem__(self, key):
        return self.data.get(key)


class LiveIRacingReaderTests(unittest.TestCase):
    def test_reads_and_orders_live_qualifying_results(self):
        reader = LiveIRacingReader(sdk_factory=FakeSdk)
        snapshot = reader.snapshot()
        self.assertTrue(snapshot["connected"])
        self.assertTrue(snapshot["provisional"])
        self.assertEqual(snapshot["session_name"], "QUALIFY")
        self.assertEqual([row["name"] for row in snapshot["drivers"]], ["James Coffman", "Terrence Murphy"])
        self.assertEqual(snapshot["drivers"][0]["best_lap_time"], 29.9)
        self.assertEqual(snapshot["session_time_remaining"], 508.5)
        self.assertEqual(snapshot["track_name"], "Charlotte Motor Speedway")
        self.assertEqual(snapshot["track_id"], 123)

    def test_qualifying_results_are_final_after_session_advances(self):
        sdk = FakeSdk()
        sdk.data["SessionNum"] = 0
        sdk.data["SessionInfo"] = {"Sessions": [{"SessionNum": 0, "SessionName": "RACE"}]}
        reader = LiveIRacingReader(sdk_factory=lambda: sdk)
        snapshot = reader.snapshot()
        self.assertFalse(snapshot["provisional"])
        self.assertEqual(snapshot["qualifying_source"], "QualifyResultsInfo")

    def test_ai_drivers_use_name_and_number_identity(self):
        sdk = FakeSdk()
        sdk.data["DriverInfo"]["Drivers"] = [
            {"CarIdx": 0, "UserID": -1, "UserName": "Carson Kvapil", "CarNumber": "1", "CarIsAI": 1},
            {"CarIdx": 1, "UserID": -1, "UserName": "Neil Quick", "CarNumber": "2", "CarIsAI": 1},
        ]
        sdk.data["QualifyResultsInfo"]["Results"] = [
            {"Position": 0, "CarIdx": 0, "FastestTime": 29.1},
            {"Position": 1, "CarIdx": 1, "FastestTime": 29.2},
        ]
        reader = LiveIRacingReader(sdk_factory=lambda: sdk)

        drivers = reader.snapshot()["drivers"]

        self.assertEqual([row["name"] for row in drivers], ["Carson Kvapil", "Neil Quick"])
        self.assertEqual([row["cust_id"] for row in drivers], [None, None])


if __name__ == "__main__":
    unittest.main()
