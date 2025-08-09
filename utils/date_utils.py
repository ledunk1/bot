from datetime import datetime, timedelta

def validate_date_range(start_date, end_date):
    """Validate date range inputs"""
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Check if start date is before end date
        if start >= end:
            return False
        
        # Check if end date is not in the future
        if end > datetime.now():
            return False
        
        return True
    except ValueError:
        return False

def format_timestamp(timestamp):
    """Format timestamp for display"""
    return timestamp.strftime('%Y-%m-%d %H:%M:%S')

def get_date_range_options():
    """Get predefined date range options"""
    now = datetime.now()
    return {
        '1_week': {
            'start': (now - timedelta(weeks=1)).strftime('%Y-%m-%d'),
            'end': now.strftime('%Y-%m-%d'),
            'label': 'Last 1 Week'
        },
        '1_month': {
            'start': (now - timedelta(days=30)).strftime('%Y-%m-%d'),
            'end': now.strftime('%Y-%m-%d'),
            'label': 'Last 1 Month'
        },
        '3_months': {
            'start': (now - timedelta(days=90)).strftime('%Y-%m-%d'),
            'end': now.strftime('%Y-%m-%d'),
            'label': 'Last 3 Months'
        },
        '6_months': {
            'start': (now - timedelta(days=180)).strftime('%Y-%m-%d'),
            'end': now.strftime('%Y-%m-%d'),
            'label': 'Last 6 Months'
        },
        '1_year': {
            'start': (now - timedelta(days=365)).strftime('%Y-%m-%d'),
            'end': now.strftime('%Y-%m-%d'),
            'label': 'Last 1 Year'
        },
        '2_years': {
            'start': (now - timedelta(days=730)).strftime('%Y-%m-%d'),
            'end': now.strftime('%Y-%m-%d'),
            'label': 'Last 2 Years'
        }
    }