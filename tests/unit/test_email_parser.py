"""Unit tests for email message parsing."""

import pytest

from smtp_gateway.email.parser import parse_email_message


@pytest.mark.unit
class TestEmailParser:
    """Tests for email message parsing (Story 2.4)."""

    def test_parse_simple_email(self):
        """Test parsing a simple plain text email."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Test Email

This is a test email body.
"""
        result = parse_email_message(email_content)

        assert result["from"] == "sender@example.com"
        assert result["to"] == ["recipient@example.com"]
        assert result["cc"] == []
        assert result["bcc"] == []
        assert result["subject"] == "Test Email"
        assert result["body_text"] == "This is a test email body.\n"

    def test_parse_email_with_empty_subject(self):
        """Test parsing email with empty subject."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject:

Email body without subject.
"""
        result = parse_email_message(email_content)

        assert result["from"] == "sender@example.com"
        assert result["to"] == ["recipient@example.com"]
        assert result["subject"] == ""
        assert result["body_text"] == "Email body without subject.\n"

    def test_parse_email_missing_subject(self):
        """Test parsing email without Subject header."""
        email_content = b"""From: sender@example.com
To: recipient@example.com

Email body without subject header.
"""
        result = parse_email_message(email_content)

        assert result["from"] == "sender@example.com"
        assert result["to"] == ["recipient@example.com"]
        assert result["subject"] == ""  # Defaults to empty string
        assert result["body_text"] == "Email body without subject header.\n"

    def test_parse_email_missing_from(self):
        """Test that missing From header raises error."""
        email_content = b"""To: recipient@example.com
Subject: Test

Body content
"""
        with pytest.raises(ValueError, match="Missing required header: From"):
            parse_email_message(email_content)

    def test_parse_email_missing_to(self):
        """Test that missing To/CC/BCC headers raises error."""
        email_content = b"""From: sender@example.com
Subject: Test

Body content
"""
        with pytest.raises(ValueError, match="At least one recipient required"):
            parse_email_message(email_content)

    def test_parse_email_with_multiple_lines(self):
        """Test parsing email with multi-line body."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Multi-line Email

This is line 1.
This is line 2.
This is line 3.

End of email.
"""
        result = parse_email_message(email_content)

        expected_body = "This is line 1.\nThis is line 2.\nThis is line 3.\n\nEnd of email.\n"
        assert result["body_text"] == expected_body

    def test_parse_email_with_content_type(self):
        """Test parsing email with explicit Content-Type: text/plain."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Typed Email
Content-Type: text/plain; charset=utf-8

Body with explicit content type.
"""
        result = parse_email_message(email_content)

        assert result["from"] == "sender@example.com"
        assert result["to"] == ["recipient@example.com"]
        assert result["body_text"] == "Body with explicit content type.\n"

    def test_parse_email_with_utf8_content(self):
        """Test parsing email with UTF-8 characters."""
        # Use proper RFC 2047 encoding for subject with special characters
        import base64
        subject_text = "UTF-8 Test ☺"
        subject_encoded = base64.b64encode(subject_text.encode("utf-8")).decode("ascii")

        email_content = f"""From: sender@example.com
To: recipient@example.com
Subject: =?utf-8?B?{subject_encoded}?=
Content-Type: text/plain; charset=utf-8

Hello world! 你好世界 🌍
""".encode("utf-8")

        result = parse_email_message(email_content)

        assert result["subject"] == "UTF-8 Test ☺"
        assert "你好世界" in result["body_text"]
        assert "🌍" in result["body_text"]

    def test_parse_email_with_latin1_charset(self):
        """Test parsing email with latin-1 charset."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Latin-1 Test
Content-Type: text/plain; charset=iso-8859-1

Caf\xe9 and na\xefve
"""
        result = parse_email_message(email_content)

        assert "Café" in result["body_text"]
        assert "naïve" in result["body_text"]

    def test_parse_email_html_single_part(self):
        """Test parsing single-part HTML email (Story 3.2)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: HTML Email
Content-Type: text/html

<html><body>HTML content</body></html>
"""
        result = parse_email_message(email_content)

        # Story 3.2: HTML is now supported
        assert result["body_text"] == ""  # No plain text part
        assert result["body_html"] == "<html><body>HTML content</body></html>\n"

    def test_parse_multipart_alternative_email(self):
        """Test parsing multipart/alternative email (Story 3.2)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Multipart Email
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/plain

Plain text part.
--boundary123
Content-Type: text/html

<html>HTML part</html>
--boundary123--
"""
        result = parse_email_message(email_content)

        # Story 3.2: Both plain text and HTML extracted
        assert result["body_text"] == "Plain text part."
        assert result["body_html"] == "<html>HTML part</html>"

    def test_parse_email_empty_body(self):
        """Test parsing email with empty body."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Empty Body

"""
        result = parse_email_message(email_content)

        assert result["body_text"] == ""

    def test_parse_email_with_additional_headers(self):
        """Test that additional headers are ignored."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Test
Date: Mon, 1 Jan 2024 12:00:00 +0000
Message-ID: <12345@example.com>
X-Custom-Header: custom value

Body content.
"""
        result = parse_email_message(email_content)

        # Only extract From, To, CC, BCC, Subject, body
        assert result["from"] == "sender@example.com"
        assert result["to"] == ["recipient@example.com"]
        assert result["subject"] == "Test"
        assert result["body_text"] == "Body content.\n"

    def test_parse_malformed_email(self):
        """Test parsing malformed email raises ValueError."""
        email_content = b"This is not a valid email format"

        # Should raise error due to missing headers
        with pytest.raises(ValueError):
            parse_email_message(email_content)

    def test_parse_email_with_encoded_subject(self):
        """Test parsing email with encoded subject (RFC 2047)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: =?utf-8?B?VGVzdCBTdWJqZWN0?=

Body content.
"""
        result = parse_email_message(email_content)

        # Python's email parser automatically decodes RFC 2047
        assert result["subject"] == "Test Subject"

    def test_parse_email_with_name_in_from(self):
        """Test parsing email with name in From field."""
        email_content = b"""From: John Doe <john@example.com>
To: Jane Smith <jane@example.com>
Subject: Test

Body
"""
        result = parse_email_message(email_content)

        # Full From format preserved, To extracts just email addresses
        assert "John Doe" in result["from"]
        assert "john@example.com" in result["from"]
        assert result["to"] == ["jane@example.com"]  # Story 3.1: extracts just email

    # Story 3.1: Multiple Recipient Support Tests

    def test_parse_email_with_multiple_to_recipients(self):
        """Test parsing email with multiple To recipients (Story 3.1)."""
        email_content = b"""From: sender@example.com
To: recipient1@example.com, recipient2@example.com, recipient3@example.com
Subject: Multiple Recipients

Test body.
"""
        result = parse_email_message(email_content)

        assert result["from"] == "sender@example.com"
        assert result["to"] == [
            "recipient1@example.com",
            "recipient2@example.com",
            "recipient3@example.com",
        ]
        assert result["cc"] == []
        assert result["bcc"] == []

    def test_parse_email_with_cc_recipients(self):
        """Test parsing email with CC recipients (Story 3.1)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Cc: cc1@example.com, cc2@example.com
Subject: With CC

Test body.
"""
        result = parse_email_message(email_content)

        assert result["to"] == ["recipient@example.com"]
        assert result["cc"] == ["cc1@example.com", "cc2@example.com"]
        assert result["bcc"] == []

    def test_parse_email_with_bcc_recipients(self):
        """Test parsing email with BCC recipients (Story 3.1)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Bcc: bcc1@example.com, bcc2@example.com
Subject: With BCC

Test body.
"""
        result = parse_email_message(email_content)

        assert result["to"] == ["recipient@example.com"]
        assert result["cc"] == []
        assert result["bcc"] == ["bcc1@example.com", "bcc2@example.com"]

    def test_parse_email_with_to_cc_bcc_all(self):
        """Test parsing email with To, CC, and BCC recipients (Story 3.1)."""
        email_content = b"""From: sender@example.com
To: to1@example.com, to2@example.com
Cc: cc1@example.com
Bcc: bcc1@example.com, bcc2@example.com
Subject: All Recipient Types

Test body.
"""
        result = parse_email_message(email_content)

        assert result["to"] == ["to1@example.com", "to2@example.com"]
        assert result["cc"] == ["cc1@example.com"]
        assert result["bcc"] == ["bcc1@example.com", "bcc2@example.com"]
        # Total 5 recipients

    def test_parse_email_with_cc_only(self):
        """Test parsing email with only CC recipients (Story 3.1)."""
        email_content = b"""From: sender@example.com
Cc: cc1@example.com, cc2@example.com
Subject: CC Only

Test body.
"""
        result = parse_email_message(email_content)

        assert result["to"] == []
        assert result["cc"] == ["cc1@example.com", "cc2@example.com"]
        assert result["bcc"] == []

    def test_parse_email_with_recipient_names(self):
        """Test parsing recipients with display names (Story 3.1)."""
        email_content = b"""From: sender@example.com
To: Alice <alice@example.com>, Bob Smith <bob@example.com>
Cc: Charlie <charlie@example.com>
Subject: With Names

Test body.
"""
        result = parse_email_message(email_content)

        # Should extract just email addresses, not display names
        assert result["to"] == ["alice@example.com", "bob@example.com"]
        assert result["cc"] == ["charlie@example.com"]

    # Story 3.2: HTML Email Body Support Tests

    def test_parse_html_only_email(self):
        """Test parsing email with only HTML body (Story 3.2)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: HTML Only
Content-Type: text/html; charset=utf-8

<html>
<body>
<h1>Welcome</h1>
<p>This is HTML content.</p>
</body>
</html>
"""
        result = parse_email_message(email_content)

        assert result["body_html"] is not None
        assert "<h1>Welcome</h1>" in result["body_html"]
        assert "<p>This is HTML content.</p>" in result["body_html"]
        assert result["body_text"] == ""  # No plain text

    def test_parse_multipart_alternative_prefers_text(self):
        """Test multipart/alternative with both text and HTML (Story 3.2)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Both Text and HTML
Content-Type: multipart/alternative; boundary="====boundary===="

--====boundary====
Content-Type: text/plain; charset=utf-8

This is the plain text version.

--====boundary====
Content-Type: text/html; charset=utf-8

<html><body><p>This is the <b>HTML</b> version.</p></body></html>

--====boundary====--
"""
        result = parse_email_message(email_content)

        # Both should be extracted
        assert result["body_text"] == "This is the plain text version.\n"
        assert result["body_html"] is not None
        assert "<b>HTML</b>" in result["body_html"]

    def test_parse_plain_text_only_no_html(self):
        """Test plain text email has no HTML (Story 3.2)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Plain Text Only

Just plain text, no HTML.
"""
        result = parse_email_message(email_content)

        assert result["body_text"] == "Just plain text, no HTML.\n"
        assert result["body_html"] is None

    def test_parse_multipart_with_charset(self):
        """Test multipart email with different charsets (Story 3.2)."""
        # Build email with mixed encodings
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Charset Test
Content-Type: multipart/alternative; boundary="boundary"

--boundary
Content-Type: text/plain; charset=iso-8859-1

Caf\xe9

--boundary
Content-Type: text/html; charset=utf-8

""" + "<html><body>Café</body></html>".encode("utf-8") + b"""

--boundary--
"""
        result = parse_email_message(email_content)

        # Both parts should decode correctly
        assert "Café" in result["body_text"]
        assert "Café" in result["body_html"]

    # Story 3.3: MIME Multipart Messages Tests

    def test_parse_multipart_mixed_with_text_only(self):
        """Test parsing multipart/mixed with text parts (Story 3.3)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Multipart Mixed
Content-Type: multipart/mixed; boundary="mixed-boundary"

--mixed-boundary
Content-Type: text/plain

This is the plain text content.

--mixed-boundary
Content-Type: text/html

<html><body>This is HTML content.</body></html>

--mixed-boundary--
"""
        result = parse_email_message(email_content)

        # Both text and HTML should be extracted
        assert result["body_text"] == "This is the plain text content.\n"
        assert result["body_html"] is not None
        assert "HTML content" in result["body_html"]

    def test_parse_nested_multipart_structure(self):
        """Test nested multipart structure (Story 3.3)."""
        # multipart/mixed containing multipart/alternative
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Nested Multipart
Content-Type: multipart/mixed; boundary="outer"

--outer
Content-Type: multipart/alternative; boundary="inner"

--inner
Content-Type: text/plain

Plain text version.

--inner
Content-Type: text/html

<html><body>HTML version.</body></html>

--inner--

--outer--
"""
        result = parse_email_message(email_content)

        # Should extract text and HTML from nested structure
        assert result["body_text"] == "Plain text version.\n"
        assert result["body_html"] is not None
        assert "HTML version" in result["body_html"]

    def test_parse_multipart_mixed_no_html(self):
        """Test multipart/mixed with only plain text (Story 3.3)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Mixed Plain Only
Content-Type: multipart/mixed; boundary="boundary"

--boundary
Content-Type: text/plain

Part 1 of plain text.

--boundary
Content-Type: text/plain

Part 2 of plain text.

--boundary--
"""
        result = parse_email_message(email_content)

        # Should find first text/plain part
        assert "Part 1 of plain text" in result["body_text"]
        assert result["body_html"] is None

    def test_parse_deeply_nested_multipart(self):
        """Test deeply nested multipart structure (Story 3.3)."""
        # Three levels deep: mixed -> related -> alternative
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Deep Nesting
Content-Type: multipart/mixed; boundary="level1"

--level1
Content-Type: multipart/related; boundary="level2"

--level2
Content-Type: multipart/alternative; boundary="level3"

--level3
Content-Type: text/plain

Deeply nested plain text.

--level3
Content-Type: text/html

<html><body>Deeply nested HTML.</body></html>

--level3--

--level2--

--level1--
"""
        result = parse_email_message(email_content)

        # msg.walk() should traverse all levels
        assert result["body_text"] == "Deeply nested plain text.\n"
        assert result["body_html"] is not None
        assert "Deeply nested HTML" in result["body_html"]

    # Story 3.4: File Attachment Support Tests

    def test_parse_email_with_attachment(self):
        """Test parsing email with file attachment (Story 3.4)."""
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText as MIMETextPart
        from email.mime.base import MIMEBase
        from email import encoders

        # Create multipart message
        msg = MIMEMultipart()
        msg["From"] = "sender@example.com"
        msg["To"] = "recipient@example.com"
        msg["Subject"] = "Email with Attachment"

        # Add text body
        msg.attach(MIMETextPart("This email has an attachment.", "plain"))

        # Add attachment
        attachment_content = b"Test file content"
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment_content)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename="test.txt")
        msg.attach(part)

        # Parse
        result = parse_email_message(msg.as_bytes())

        assert result["body_text"] == "This email has an attachment."
        assert len(result["attachments"]) == 1
        assert result["attachments"][0]["filename"] == "test.txt"
        assert result["attachments"][0]["content_type"] == "application/octet-stream"
        assert result["attachments"][0]["size"] == len(attachment_content)

        # Verify content is base64 encoded
        import base64
        decoded = base64.b64decode(result["attachments"][0]["content"])
        assert decoded == attachment_content

    def test_parse_email_with_multiple_attachments(self):
        """Test parsing email with multiple attachments (Story 3.4)."""
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText as MIMETextPart
        from email.mime.base import MIMEBase
        from email import encoders

        msg = MIMEMultipart()
        msg["From"] = "sender@example.com"
        msg["To"] = "recipient@example.com"
        msg["Subject"] = "Multiple Attachments"

        msg.attach(MIMETextPart("Email body", "plain"))

        # Add two attachments
        for i, filename in enumerate(["file1.pdf", "file2.doc"]):
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f"File {i} content".encode())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(part)

        result = parse_email_message(msg.as_bytes())

        assert len(result["attachments"]) == 2
        assert result["attachments"][0]["filename"] == "file1.pdf"
        assert result["attachments"][1]["filename"] == "file2.doc"

    def test_parse_email_with_image_attachment(self):
        """Test parsing email with image attachment (Story 3.4)."""
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText as MIMETextPart
        from email.mime.image import MIMEImage

        msg = MIMEMultipart()
        msg["From"] = "sender@example.com"
        msg["To"] = "recipient@example.com"
        msg["Subject"] = "Image Attachment"

        msg.attach(MIMETextPart("See attached image", "plain"))

        # Add image
        image_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR..."  # Fake PNG header
        image = MIMEImage(image_data)
        image.add_header("Content-Disposition", "attachment", filename="photo.png")
        msg.attach(image)

        result = parse_email_message(msg.as_bytes())

        assert len(result["attachments"]) == 1
        assert result["attachments"][0]["filename"] == "photo.png"
        assert "image" in result["attachments"][0]["content_type"]

    def test_parse_email_no_attachments(self):
        """Test email without attachments returns empty list (Story 3.4)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: No Attachments

Just plain text, no attachments.
"""
        result = parse_email_message(email_content)

        assert result["attachments"] == []

    # Story 3.5: Advanced Header Parsing Tests

    def test_parse_email_with_reply_to(self):
        """Test parsing Reply-To header (Story 3.5)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Reply-To: reply@example.com
Subject: With Reply-To

Email body.
"""
        result = parse_email_message(email_content)

        assert result["reply_to"] == "reply@example.com"

    def test_parse_email_with_message_id(self):
        """Test parsing Message-ID header (Story 3.5)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Message-ID: <unique-id-123@example.com>
Subject: With Message-ID

Email body.
"""
        result = parse_email_message(email_content)

        assert result["message_id"] == "<unique-id-123@example.com>"

    def test_parse_email_with_date(self):
        """Test parsing Date header (Story 3.5)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Date: Mon, 1 Jan 2024 12:00:00 +0000
Subject: With Date

Email body.
"""
        result = parse_email_message(email_content)

        assert result["date"] == "Mon, 1 Jan 2024 12:00:00 +0000"

    def test_parse_email_with_custom_headers(self):
        """Test parsing custom X-* headers (Story 3.5)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Custom Headers
X-Priority: High
X-Campaign-ID: campaign-123
X-Custom-Tag: test-value

Email body.
"""
        result = parse_email_message(email_content)

        assert "X-Priority" in result["custom_headers"]
        assert result["custom_headers"]["X-Priority"] == "High"
        assert "X-Campaign-ID" in result["custom_headers"]
        assert result["custom_headers"]["X-Campaign-ID"] == "campaign-123"
        assert "X-Custom-Tag" in result["custom_headers"]
        assert result["custom_headers"]["X-Custom-Tag"] == "test-value"

    def test_parse_email_without_optional_headers(self):
        """Test email without optional headers (Story 3.5)."""
        email_content = b"""From: sender@example.com
To: recipient@example.com
Subject: Minimal Headers

Email body.
"""
        result = parse_email_message(email_content)

        assert result["reply_to"] == ""
        assert result["message_id"] == ""
        assert result["date"] == ""
        assert result["custom_headers"] == {}

    def test_parse_email_with_all_headers(self):
        """Test email with all supported headers (Story 3.5)."""
        email_content = b"""From: sender@example.com
To: recipient1@example.com, recipient2@example.com
Cc: cc@example.com
Bcc: bcc@example.com
Reply-To: reply@example.com
Subject: Complete Email
Date: Mon, 1 Jan 2024 12:00:00 +0000
Message-ID: <msg-id-456@example.com>
X-Mailer: CustomMailer/1.0
X-Priority: 1

Email body with all headers.
"""
        result = parse_email_message(email_content)

        # Verify all headers parsed
        assert result["from"] == "sender@example.com"
        assert len(result["to"]) == 2
        assert len(result["cc"]) == 1
        assert len(result["bcc"]) == 1
        assert result["reply_to"] == "reply@example.com"
        assert result["subject"] == "Complete Email"
        assert result["date"] == "Mon, 1 Jan 2024 12:00:00 +0000"
        assert result["message_id"] == "<msg-id-456@example.com>"
        assert "X-Mailer" in result["custom_headers"]
        assert "X-Priority" in result["custom_headers"]
