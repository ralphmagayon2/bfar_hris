# apps/leaves/csc_conversion.py
from decimal import Decimal

# Exact CSC Omnibus Rules on Leave (Rule XVI) Conversion Table
CSC_MINUTE_CONVERSION = {
    0: '0.000', 1: '0.002', 2: '0.004', 3: '0.006', 4: '0.008', 5: '0.010',
    6: '0.012', 7: '0.015', 8: '0.017', 9: '0.019', 10: '0.021', 11: '0.023',
    12: '0.025', 13: '0.027', 14: '0.029', 15: '0.031', 16: '0.033', 17: '0.035',
    18: '0.037', 19: '0.040', 20: '0.042', 21: '0.044', 22: '0.046', 23: '0.048',
    24: '0.050', 25: '0.052', 26: '0.054', 27: '0.056', 28: '0.058', 29: '0.060',
    30: '0.062', 31: '0.065', 32: '0.067', 33: '0.069', 34: '0.071', 35: '0.073',
    36: '0.075', 37: '0.077', 38: '0.079', 39: '0.081', 40: '0.083', 41: '0.085',
    42: '0.087', 43: '0.090', 44: '0.092', 45: '0.094', 46: '0.096', 47: '0.098',
    48: '0.100', 49: '0.102', 50: '0.104', 51: '0.106', 52: '0.108', 53: '0.110',
    54: '0.112', 55: '0.115', 56: '0.117', 57: '0.119', 58: '0.121', 59: '0.123'
}

def get_deduction_days(total_minutes: int) -> Decimal:
    """
    Converts total monthly late/undertime minutes into exact leave days 
    following the CSC conversion formula (1 hour = 0.125 days).
    """
    if not total_minutes or total_minutes <= 0:
        return Decimal('0.000')

    hours = total_minutes // 60
    minutes = total_minutes % 60

    # 1 hour = 0.125 days
    hour_equiv = Decimal(str(hours)) * Decimal('0.125')
    minute_equiv = Decimal(CSC_MINUTE_CONVERSION.get(minutes, '0.000'))

    return hour_equiv + minute_equiv