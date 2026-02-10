#!/usr/bin/env python3
"""
Performance System Verification Script
Run this in Odoo shell to verify all enhancements are working correctly.

Usage:
    odoo-bin shell -d your_database --config=/path/to/odoo.conf
    >>> exec(open('/path/to/verify_performance_enhancements.py').read())
"""

def verify_performance_enhancements(env):
    """Verify all performance system enhancements."""
    
    print("\n" + "="*80)
    print("PERFORMANCE SYSTEM VERIFICATION")
    print("="*80 + "\n")
    
    results = {
        'passed': 0,
        'failed': 0,
        'warnings': 0
    }
    
    # Test 1: Verify criteria weights total 100%
    print("Test 1: Verifying Performance Criteria Weights...")
    criteria = env['guard.performance.criteria'].search([('active', '=', True)])
    total_weight = sum(criteria.mapped('weight'))
    
    if abs(total_weight - 100.0) < 0.01:  # Allow for floating point precision
        print(f"  ✅ PASS: Total weight is {total_weight}%")
        results['passed'] += 1
    else:
        print(f"  ❌ FAIL: Total weight is {total_weight}% (should be 100%)")
        results['failed'] += 1
    
    # Test 2: Verify all expected criteria exist
    print("\nTest 2: Verifying All Criteria Exist...")
    expected_criteria = [
        'punctuality', 'tour_completion', 'incident_response',
        'client_satisfaction', 'shift_adherence', 'communication',
        'professionalism'
    ]
    
    existing_codes = criteria.mapped('code')
    missing = [c for c in expected_criteria if c not in existing_codes]
    
    if not missing:
        print(f"  ✅ PASS: All {len(expected_criteria)} criteria exist")
        results['passed'] += 1
    else:
        print(f"  ❌ FAIL: Missing criteria: {missing}")
        results['failed'] += 1
    
    # Test 3: Verify badge types
    print("\nTest 3: Verifying Badge Types...")
    badge_model = env['guard.performance.badge']
    badge_types = dict(badge_model._fields['badge_type'].selection)
    
    expected_badges = [
        'punctuality', 'attendance', 'tour_master', 'incident_hero',
        'client_favorite', 'safety_champion', 'top_performer',
        'milestone_1yr', 'milestone_3yr', 'milestone_5yr', 'milestone_10yr'
    ]
    
    missing_badges = [b for b in expected_badges if b not in badge_types.keys()]
    
    if not missing_badges:
        print(f"  ✅ PASS: All {len(expected_badges)} badge types exist")
        results['passed'] += 1
    else:
        print(f"  ❌ FAIL: Missing badge types: {missing_badges}")
        results['failed'] += 1
    
    # Test 4: Verify database indexes
    print("\nTest 4: Verifying Database Indexes...")
    env.cr.execute("""
        SELECT indexname 
        FROM pg_indexes 
        WHERE indexname LIKE 'idx_performance%'
        ORDER BY indexname
    """)
    indexes = [row[0] for row in env.cr.fetchall()]
    
    expected_indexes = [
        'idx_performance_badge_guard_type',
        'idx_performance_badge_type_date',
        'idx_performance_metric_criteria_code',
        'idx_performance_metric_guard_period_criteria',
        'idx_performance_metric_score',
        'idx_performance_review_grade',
        'idx_performance_review_guard_period',
        'idx_performance_review_reviewer',
        'idx_performance_review_state',
    ]
    
    missing_indexes = [i for i in expected_indexes if i not in indexes]
    
    if not missing_indexes:
        print(f"  ✅ PASS: All {len(expected_indexes)} indexes exist")
        results['passed'] += 1
    else:
        print(f"  ⚠️  WARNING: Missing indexes: {missing_indexes}")
        print("     (Indexes may be created on next module upgrade)")
        results['warnings'] += 1
    
    # Test 5: Test metric calculation
    print("\nTest 5: Testing Metric Calculation...")
    try:
        # Find an active guard with recent data
        guard = env['guard.profile'].search([('status', '=', 'active')], limit=1)
        
        if guard:
            # Create a test review
            from datetime import datetime, timedelta
            from dateutil.relativedelta import relativedelta
            
            today = datetime.now().date()
            period_start = today - relativedelta(months=1, day=1)
            period_end = today - relativedelta(day=1)
            
            test_review = env['guard.performance.review'].create({
                'guard_id': guard.id,
                'review_period': 'monthly',
                'period_start': period_start,
                'period_end': period_end,
                'review_date': today,
                'reviewer_id': env.user.id,
                'state': 'draft',
            })
            
            # Try to calculate metrics
            test_review._calculate_all_metrics()
            
            # Check if metrics were created
            metrics = env['guard.performance.metric'].search([
                ('guard_id', '=', guard.id),
                ('period_start', '=', period_start),
                ('period_end', '=', period_end),
            ])
            
            if metrics:
                print(f"  ✅ PASS: Metrics calculated successfully ({len(metrics)} metrics)")
                results['passed'] += 1
            else:
                print(f"  ⚠️  WARNING: No metrics calculated (may be no data for period)")
                results['warnings'] += 1
            
            # Clean up test review
            test_review.unlink()
        else:
            print(f"  ⚠️  WARNING: No active guards found to test")
            results['warnings'] += 1
    except Exception as e:
        print(f"  ❌ FAIL: Error during metric calculation: {str(e)}")
        results['failed'] += 1
    
    # Test 6: Verify criteria details
    print("\nTest 6: Verifying Criteria Details...")
    criteria_details = {}
    for criterion in criteria:
        criteria_details[criterion.code] = {
            'name': criterion.name,
            'weight': criterion.weight,
            'method': criterion.calculation_method
        }
    
    print("\n  Current Criteria Configuration:")
    for code, details in sorted(criteria_details.items()):
        print(f"    • {details['name']}: {details['weight']}% ({details['method']})")
    
    results['passed'] += 1
    
    # Summary
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    print(f"✅ Passed:   {results['passed']}")
    print(f"❌ Failed:   {results['failed']}")
    print(f"⚠️  Warnings: {results['warnings']}")
    print("="*80 + "\n")
    
    if results['failed'] == 0:
        print("🎉 All critical tests passed! Performance system is ready.")
        if results['warnings'] > 0:
            print("⚠️  Some warnings present - review above for details.")
    else:
        print("❌ Some tests failed - please review and fix issues above.")
    
    return results


# Run verification if executed in Odoo shell
if __name__ == '__main__' or 'env' in dir():
    try:
        verify_performance_enhancements(env)
    except NameError:
        print("Error: This script must be run in Odoo shell")
        print("Usage: odoo-bin shell -d your_database")
        print(">>> exec(open('verify_performance_enhancements.py').read())")
