"""Email utility functions for sending emails with various content types.

This module provides functionality for sending emails with support for:
- Multiple content types (text, HTML, markdown)
- File attachments
- Pandas DataFrame conversion
- Secure SMTP configuration
"""

import os
import smtplib
import logging
from email import encoders
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, List, Union, Optional
from io import StringIO
import pandas as pd
import markdown


def _convert_to_html(content: object) -> str:
    """Convert various Python objects to HTML representation.

    Args:
        content: The object to convert (str, DataFrame, dict, list, etc.)

    Returns:
        str: HTML representation of the object
    """
    if isinstance(content, pd.DataFrame):
        return content.to_html(index=True, classes='dataframe')
    elif isinstance(content, (dict, list)):
        return f"<pre>{str(content)}</pre>"
    elif isinstance(content, str):
        return markdown.markdown(content)
    else:
        return f"<pre>{str(content)}</pre>"


def _parse_email_addresses(addresses: Union[str, List[str]]) -> List[str]:
    """Parse and normalize email addresses.

    Args:
        addresses: Single email address or list of addresses

    Returns:
        List[str]: List of normalized email addresses
    """
    if isinstance(addresses, str):
        # Split on common separators
        for sep in [';', ',']:
            if sep in addresses:
                addresses = addresses.split(sep)
                break
        if isinstance(addresses, str):
            addresses = [addresses]
    
    # Clean and validate addresses
    cleaned = [addr.strip() for addr in addresses]
    return [addr for addr in cleaned if '@' in addr]


def send_email(
    from_address: str,
    to_address: Union[str, List[str]],
    subject: str,
    email_contents: List[object],
    attachments: Optional[Dict[str, Union[str, bytes]]] = None,
    smtp_host: str = 'smtp.gmail.com',
    smtp_port: int = 587,
    smtp_username: Optional[str] = None,
    smtp_password: Optional[str] = None,
    use_tls: bool = True,
) -> None:
    """Send an email with various content types and attachments.

    Args:
        from_address: Sender's email address
        to_address: Recipient email address(es)
        subject: Email subject
        email_contents: List of content objects to include in email body
        attachments: Dictionary of attachment filename to content mappings
        smtp_host: SMTP server hostname
        smtp_port: SMTP server port
        smtp_username: SMTP authentication username (if None, uses from_address)
        smtp_password: SMTP authentication password
        use_tls: Whether to use TLS encryption

    Raises:
        ValueError: If email addresses are invalid
        smtplib.SMTPException: If SMTP connection or sending fails
    """
    # Validate and parse email addresses
    from_addr = _parse_email_addresses(from_address)
    if not from_addr:
        raise ValueError(f"Invalid from_address: {from_address}")
    from_addr = from_addr[0]

    to_addrs = _parse_email_addresses(to_address)
    if not to_addrs:
        raise ValueError(f"Invalid to_address: {to_address}")

    # Create message container
    msg = MIMEMultipart('alternative')
    msg['From'] = from_addr
    msg['To'] = ', '.join(to_addrs)
    msg['Subject'] = subject

    # Create HTML email body
    html_template = """
    <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; }
                .dataframe {
                    border-collapse: collapse;
                    margin: 10px 0;
                    font-size: 0.9em;
                    min-width: 400px;
                    box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
                }
                .dataframe thead tr {
                    background-color: #009879;
                    color: #ffffff;
                    text-align: left;
                }
                .dataframe th,
                .dataframe td {
                    padding: 12px 15px;
                    border: 1px solid #dddddd;
                }
                .dataframe tbody tr:nth-of-type(even) {
                    background-color: #f3f3f3;
                }
                pre {
                    background-color: #f5f5f5;
                    padding: 15px;
                    border-radius: 5px;
                    overflow-x: auto;
                }
            </style>
        </head>
        <body>
            __BODY__
        </body>
    </html>
    """

    # Convert contents to HTML
    body_parts = [_convert_to_html(content) for content in email_contents]
    html_body = html_template.replace('__BODY__', '\n'.join(body_parts))
    
    # Attach HTML body
    msg.attach(MIMEText(html_body, 'html'))

    # Handle attachments
    if attachments:
        for filename, content in attachments.items():
            if isinstance(content, str) and os.path.exists(content):
                # File path attachment
                with open(content, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
            elif isinstance(content, str):
                # String content attachment
                part = MIMEApplication(content.encode('utf-8'))
            elif isinstance(content, bytes):
                # Binary content attachment
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(content)
            else:
                logging.warning(f"Skipping invalid attachment: {filename}")
                continue

            # Encode and add header
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                'attachment',
                filename=os.path.basename(filename)
            )
            msg.attach(part)

    # Setup SMTP connection
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if use_tls:
                server.starttls()
            
            # Login if credentials provided
            if smtp_password:
                username = smtp_username or from_addr
                server.login(username, smtp_password)

            # Send email
            server.sendmail(from_addr, to_addrs, msg.as_string())
            logging.info(f"Email sent successfully to {', '.join(to_addrs)}")

    except smtplib.SMTPException as e:
        logging.error(f"Failed to send email: {str(e)}")
        raise