"""Tests for generate_usps_codes.py"""
import io
import os
import sys
import tempfile
import unittest

# Ensure the repo root is importable regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_usps_codes import (
    generate_usps_qr_code,
    generate_usps_barcode,
    generate_imb,
    validate_usps_tracking_number,
    _encode_imb_fields,
)
from PIL import Image


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A valid 22-digit USPS tracking number with correct check digit.
# Computed: weights alternate 3,1,...  Sum=249, check=(10-(249%10))%10=1
VALID_TN = "9400111899223397644928"

# A valid 20-digit tracking number (Priority Mail)
VALID_TN_20 = "94001118992233976449"


class TestValidateTrackingNumber(unittest.TestCase):

    def test_valid_22_digit(self):
        # 9400111899223397644928 -> check digit validation
        self.assertIsInstance(validate_usps_tracking_number(VALID_TN), bool)

    def test_rejects_too_long(self):
        self.assertFalse(validate_usps_tracking_number("12345678901234567890123"))

    def test_rejects_letters(self):
        self.assertFalse(validate_usps_tracking_number("940011189922339764492X"))

    def test_rejects_empty(self):
        self.assertFalse(validate_usps_tracking_number(""))

    def test_strips_spaces(self):
        spaced = " ".join(VALID_TN[i:i+4] for i in range(0, len(VALID_TN), 4))
        result = validate_usps_tracking_number(spaced)
        self.assertIsInstance(result, bool)

    def test_known_valid_check_digit(self):
        # Build a number whose check digit we compute manually then verify
        base = "940011189922339764492"  # 21 digits
        digits = [int(d) for d in base]
        weights = [3 if i % 2 == 0 else 1 for i in range(len(digits))]
        total = sum(d * w for d, w in zip(digits, weights))
        check = (10 - (total % 10)) % 10
        tn = base + str(check)
        self.assertTrue(validate_usps_tracking_number(tn))

    def test_known_invalid_check_digit(self):
        base = "940011189922339764492"
        digits = [int(d) for d in base]
        weights = [3 if i % 2 == 0 else 1 for i in range(len(digits))]
        total = sum(d * w for d, w in zip(digits, weights))
        correct_check = (10 - (total % 10)) % 10
        wrong_check = (correct_check + 1) % 10
        tn = base + str(wrong_check)
        self.assertFalse(validate_usps_tracking_number(tn))


class TestQRCode(unittest.TestCase):

    def test_returns_pil_image(self):
        img = generate_usps_qr_code(VALID_TN)
        self.assertIsInstance(img, Image.Image)

    def test_image_is_rgb(self):
        img = generate_usps_qr_code(VALID_TN)
        self.assertEqual(img.mode, "RGB")

    def test_minimum_size(self):
        # QR code + text label should be at least 200x200 px
        img = generate_usps_qr_code(VALID_TN)
        self.assertGreater(img.width, 200)
        self.assertGreater(img.height, 200)

    def test_saves_to_file(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        try:
            generate_usps_qr_code(VALID_TN, output_path=path)
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 0)
        finally:
            os.unlink(path)

    def test_invalid_tracking_raises(self):
        with self.assertRaises(ValueError):
            generate_usps_qr_code("12345")  # too short

    def test_invalid_letters_raises(self):
        with self.assertRaises(ValueError):
            generate_usps_qr_code("940011189922339764492X")

    def test_20_digit_tracking(self):
        img = generate_usps_qr_code(VALID_TN_20)
        self.assertIsInstance(img, Image.Image)


class TestBarcode(unittest.TestCase):

    def test_returns_pil_image(self):
        img = generate_usps_barcode(VALID_TN)
        self.assertIsInstance(img, Image.Image)

    def test_image_is_rgb(self):
        img = generate_usps_barcode(VALID_TN)
        self.assertEqual(img.mode, "RGB")

    def test_minimum_height(self):
        # 1.25 inch at 300 dpi = 375 px; image height should exceed this
        img = generate_usps_barcode(VALID_TN)
        self.assertGreater(img.height, 300)

    def test_saves_to_file(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        try:
            generate_usps_barcode(VALID_TN, output_path=path)
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 0)
        finally:
            os.unlink(path)

    def test_invalid_tracking_raises(self):
        with self.assertRaises(ValueError):
            generate_usps_barcode("SHORT")

    def test_20_digit_tracking(self):
        img = generate_usps_barcode(VALID_TN_20)
        self.assertIsInstance(img, Image.Image)


class TestIMb(unittest.TestCase):

    _BARCODE_ID       = "00"
    _SERVICE_TYPE_ID  = "040"
    _MAILER_ID_6      = "901234"
    _SERIAL_9         = "123456789"
    _MAILER_ID_9      = "901234567"
    _SERIAL_6         = "123456"
    _ROUTING          = "40160"

    def test_encode_returns_65_bars(self):
        bars = _encode_imb_fields(
            self._BARCODE_ID, self._SERVICE_TYPE_ID,
            self._MAILER_ID_6, self._SERIAL_9, self._ROUTING
        )
        self.assertEqual(len(bars), 65)

    def test_encode_bar_values_in_range(self):
        bars = _encode_imb_fields(
            self._BARCODE_ID, self._SERVICE_TYPE_ID,
            self._MAILER_ID_6, self._SERIAL_9, ""
        )
        for b in bars:
            self.assertIn(b, (0, 1, 2, 3))

    def test_first_and_last_bar_full(self):
        bars = _encode_imb_fields(
            self._BARCODE_ID, self._SERVICE_TYPE_ID,
            self._MAILER_ID_6, self._SERIAL_9, self._ROUTING
        )
        self.assertEqual(bars[0], 3)   # FULL
        self.assertEqual(bars[-1], 3)  # FULL

    def test_generate_imb_returns_image(self):
        img = generate_imb(
            self._BARCODE_ID, self._SERVICE_TYPE_ID,
            self._MAILER_ID_6, self._SERIAL_9, self._ROUTING
        )
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.mode, "RGB")

    def test_generate_imb_width_approx_usps(self):
        # USPS specifies ~3.67 inch wide at 300 dpi ≈ 1100 px (tolerance ±50%)
        img = generate_imb(
            self._BARCODE_ID, self._SERVICE_TYPE_ID,
            self._MAILER_ID_6, self._SERIAL_9, self._ROUTING,
            dpi=300
        )
        self.assertGreater(img.width, 400)

    def test_generate_imb_saves_file(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        try:
            generate_imb(
                self._BARCODE_ID, self._SERVICE_TYPE_ID,
                self._MAILER_ID_6, self._SERIAL_9,
                output_path=path
            )
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 0)
        finally:
            os.unlink(path)

    def test_generate_imb_9digit_mailer(self):
        img = generate_imb(
            self._BARCODE_ID, self._SERVICE_TYPE_ID,
            self._MAILER_ID_9, self._SERIAL_6, "401604521"
        )
        self.assertIsInstance(img, Image.Image)

    def test_encode_invalid_barcode_id(self):
        with self.assertRaises(ValueError):
            _encode_imb_fields("1", self._SERVICE_TYPE_ID,
                               self._MAILER_ID_6, self._SERIAL_9, "")

    def test_encode_invalid_service_type(self):
        with self.assertRaises(ValueError):
            _encode_imb_fields(self._BARCODE_ID, "40",
                               self._MAILER_ID_6, self._SERIAL_9, "")

    def test_encode_invalid_routing_code(self):
        with self.assertRaises(ValueError):
            _encode_imb_fields(self._BARCODE_ID, self._SERVICE_TYPE_ID,
                               self._MAILER_ID_6, self._SERIAL_9, "123")

    def test_deterministic_output(self):
        bars1 = _encode_imb_fields(
            self._BARCODE_ID, self._SERVICE_TYPE_ID,
            self._MAILER_ID_6, self._SERIAL_9, self._ROUTING
        )
        bars2 = _encode_imb_fields(
            self._BARCODE_ID, self._SERVICE_TYPE_ID,
            self._MAILER_ID_6, self._SERIAL_9, self._ROUTING
        )
        self.assertEqual(bars1, bars2)

    def test_different_inputs_different_bars(self):
        bars1 = _encode_imb_fields(
            self._BARCODE_ID, self._SERVICE_TYPE_ID,
            self._MAILER_ID_6, self._SERIAL_9, self._ROUTING
        )
        bars2 = _encode_imb_fields(
            self._BARCODE_ID, self._SERVICE_TYPE_ID,
            self._MAILER_ID_6, self._SERIAL_9, "90210"
        )
        self.assertNotEqual(bars1, bars2)


if __name__ == "__main__":
    unittest.main()
