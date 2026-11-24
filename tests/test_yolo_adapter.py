import unittest
from types import SimpleNamespace

import numpy as np

from app.detectors import YoloDetector
from app.protocol import WasteType


class _Scalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class _Coordinates:
    def __init__(self, values):
        self.values = np.asarray(values, dtype=np.float32)

    def cpu(self):
        return self

    def numpy(self):
        return self.values


class _Box:
    def __init__(self, confidence, class_id, coordinates):
        self.conf = _Scalar(confidence)
        self.cls = _Scalar(class_id)
        self.xyxy = [_Coordinates(coordinates)]


class _Result:
    def __init__(self, names, boxes):
        self.names = names
        self.boxes = boxes


class _FakeModel:
    def __init__(self, result):
        self.names = result.names
        self.result = result

    def predict(self, **kwargs):
        return [self.result]


class YoloDetectorAdapterTests(unittest.TestCase):
    def test_multiple_detections_are_converted_and_sorted(self):
        names = {0: "battery", 1: "potato", 2: "bottolad"}
        result = _Result(
            names,
            [
                _Box(0.61, 1, [5, 6, 30, 40]),
                _Box(0.93, 0, [10, 20, 80, 120]),
                _Box(0.49, 2, [1, 2, 3, 4]),
            ],
        )
        detector = YoloDetector(model=_FakeModel(result), confidence=0.5)

        output = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))

        self.assertEqual([item.class_name for item in output], ["battery", "potato"])
        self.assertEqual(output[0].waste_type, WasteType.HAZARDOUS)
        self.assertEqual(output[1].waste_type, WasteType.KITCHEN)
        self.assertEqual(output[0].box, (10, 20, 80, 120))

    def test_empty_batch_returns_no_detections(self):
        names = {0: "battery"}
        boxes = SimpleNamespace(
            xyxy=np.empty((0, 4), dtype=np.float32),
            conf=np.empty((0,), dtype=np.float32),
            cls=np.empty((0,), dtype=np.float32),
        )
        detector = YoloDetector(model=_FakeModel(_Result(names, boxes)))

        self.assertEqual(
            detector.detect(np.zeros((32, 32, 3), dtype=np.uint8)),
            [],
        )

    def test_real_ultralytics_batch_arrays_are_supported(self):
        names = {0: "battery", 1: "potato"}
        boxes = SimpleNamespace(
            xyxy=np.asarray([[10, 20, 80, 120], [2, 3, 40, 50]]),
            conf=np.asarray([0.82, 0.95]),
            cls=np.asarray([0, 1]),
        )
        detector = YoloDetector(model=_FakeModel(_Result(names, boxes)))

        output = detector.detect(np.zeros((100, 100, 3), dtype=np.uint8))

        self.assertEqual([item.class_name for item in output], ["potato", "battery"])
        self.assertEqual(output[0].box, (2, 3, 40, 50))
        self.assertAlmostEqual(output[0].confidence, 0.95)


if __name__ == "__main__":
    unittest.main()
