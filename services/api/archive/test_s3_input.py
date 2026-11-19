from datetime import datetime, timezone

import pytest

from archive.s3_input import S3Client, S3Error, sign

# The public example credentials from the AWS Signature Version 4 documentation (not a real account).
AWS_DOC_KEY = "AKIA" + "IOSFODNN7EXAMPLE"  # ggignore
AWS_DOC_SECRET = "wJalrXUtnFEMI/K7MDENG/" + "bPxRfiCYEXAMPLEKEY"  # ggignore



def test_signature_matches_the_aws_documentation_example():
    # "Example: GET Object" from the AWS Signature Version 4 documentation for Amazon S3.
    headers = sign("GET", "https://examplebucket.s3.amazonaws.com/test.txt", {"Range": "bytes=0-9"},
                   access_key=AWS_DOC_KEY, secret_key=AWS_DOC_SECRET,
                   region="us-east-1", now=datetime(2013, 5, 24, tzinfo=timezone.utc))
    assert headers["Authorization"] == (
        f"AWS4-HMAC-SHA256 Credential={AWS_DOC_KEY}/20130524/us-east-1/s3/aws4_request, "
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date, "
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41")  # ggignore (published test vector)


def test_client_validates_endpoints_and_builds_both_address_styles():
    with pytest.raises(S3Error):
        S3Client(endpoint="ftp://x", bucket="b", access_key="a", secret_key="s")
    virtual = S3Client(endpoint="https://s3.eu-west-1.amazonaws.com", bucket="scans", access_key="a", secret_key="s", addressing="virtual")
    assert virtual._url("inbox/a b.pdf") == "https://scans.s3.eu-west-1.amazonaws.com/inbox/a%20b.pdf"
    path = S3Client(endpoint="http://nas.local:9000", bucket="scans", access_key="a", secret_key="s")
    assert path._url("inbox/è+più.pdf") == "http://nas.local:9000/scans/inbox/%C3%A8%2Bpi%C3%B9.pdf"
