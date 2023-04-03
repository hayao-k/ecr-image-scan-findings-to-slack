"""
This is a sample function to send ECR Image ScanFindings to slack.
I am not responsible for any trouble that may occur.
Environment variables:
    CHANNEL: Slack channel name
    WEBHOOK_URL: Incoming Webhook URL
"""

from datetime import datetime
from logging import getLogger, INFO
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json
import os
from botocore.exceptions import ClientError
import boto3

logger = getLogger()
logger.setLevel(INFO)

def get_properties(finding_counts):
    """Returns the color setting of severity"""
    if finding_counts['CRITICAL'] != 0:
        properties = {'color': 'danger', 'icon': ':red_circle:'}
    elif finding_counts['HIGH'] != 0:
        properties = {'color': 'warning', 'icon': ':large_orange_diamond:'}
    else:
        properties = {'color': 'good', 'icon': ':green_heart:'}
    return properties

def get_params(scan_result):
    """Slack message formatting"""
    region = os.environ['AWS_DEFAULT_REGION']
    channel = os.environ['CHANNEL']
    severity_list = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFORMAL', 'UNDEFINED']
    finding_counts = scan_result['imageScanFindingsSummary']['findingSeverityCounts']

    for severity in severity_list:
        finding_counts.setdefault(severity, 0)

    message = f"*ECR Image Scan findings | {region} | Account:{scan_result['registryId']}*"
    description = scan_result['imageScanStatus']['description']
    text_properties = get_properties(finding_counts)

    complete_at = datetime.strftime(
        scan_result['imageScanFindingsSummary']['imageScanCompletedAt'],
        '%Y-%m-%d %H:%M:%S %Z'
    )
    source_update_at = datetime.strftime(
        scan_result['imageScanFindingsSummary']['vulnerabilitySourceUpdatedAt'],
        '%Y-%m-%d %H:%M:%S %Z'
    )

    slack_message = {
        'username': 'Amazon ECR',
        'channels': channel,
        'icon_emoji': ':ecr:',
        'text': message,
        'attachments': [
            {
                'fallback': 'AmazonECR Image Scan Findings Description.',
                'color': text_properties['color'],
                'title': f'''{text_properties['icon']} {
                    scan_result['repositoryName']}:{
                    scan_result['image-tags'][0]}''',
                'title_link': f'''https://{region}.console.aws.amazon.com/ecr/repositories/private/{
                    scan_result['registryId']}/{scan_result['repositoryName']}/_/image/{
                    scan_result['imageDigest']}/scan-results?region={region}''',
                'text': f'''{description}\nImage Scan Completed at {
                    complete_at}\nVulnerability Source Updated at {source_update_at}''',
                'fields': [
                    {'title': 'Critical', 'value': finding_counts['CRITICAL'], 'short': True},
                    {'title': 'High', 'value': finding_counts['HIGH'], 'short': True},
                    {'title': 'Medium', 'value': finding_counts['MEDIUM'], 'short': True},
                    {'title': 'Low', 'value': finding_counts['LOW'], 'short': True},
                    {'title': 'Informational', 'value': finding_counts['INFORMAL'], 'short': True},
                    {'title': 'Undefined', 'value': finding_counts['UNDEFINED'], 'short': True},
                ]
            }
        ]
    }
    return slack_message

def get_findings(detail):
    """Returns the image scan findings summary"""
    ecr = boto3.client('ecr')
    try:
        response = ecr.describe_images(
            repositoryName=detail['repository-name'],
            imageIds=[
                {'imageDigest': detail['image-digest']}
            ]
        )
    except ClientError as err:
        logger.error("Request failed: %s", err.response['Error']['Message'])
    else:
        return response['imageDetails'][0]

def lambda_handler(event, context):
    """AWS Lambda Function to send ECR Image Scan Findings to Slack"""
    response = 1
    scan_result = get_findings(event['detail'])
    slack_message = get_params(scan_result)
    req = Request(os.environ['WEBHOOK_URL'], json.dumps(slack_message).encode('utf-8'))
    try:
        with urlopen(req) as res:
            res.read()
            logger.info("Message posted.")
    except HTTPError as err:
        logger.error("Request failed: %d %s", err.code, err.reason)
    except URLError as err:
        logger.error("Server connection failed: %s", err.reason)
    else:
        response = 0

    return response
