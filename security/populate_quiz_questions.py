"""
Populate Quiz Question Data - Simple Script

Run this script to add test question-level data to existing quiz attempts.

Usage:
1. Stop Odoo: sudo docker-compose stop odoo_security
2. Run this script: sudo docker-compose run --rm odoo_security odoo shell -c /etc/odoo/odoo.conf -d security
3. Then paste this entire script
4. Start Odoo: sudo docker-compose start odoo_security
"""

import random
from odoo.exceptions import UserError

# Find quiz attempts without question details
quiz_attempts = env['slide.slide.partner'].search([
    ('slide_id.slide_category', '=', 'quiz'),
    ('completed', '=', True),
    ('quiz_line_ids', '=', False)
], limit=100)

print(f"\n{'='*60}")
print(f"Found {len(quiz_attempts)} quiz attempts to populate")
print(f"{'='*60}\n")

populated_count = 0
skipped_count = 0

for attempt in quiz_attempts:
    slide = attempt.slide_id
    questions = slide.question_ids if hasattr(slide, 'question_ids') else []
    
    if not questions:
        print(f"⚠ Skipping {slide.name} - No questions")
        skipped_count += 1
        continue
    
    quiz_lines = []
    correct_count = 0
    
    for question in questions:
        # Get answer options
        answer_records = (
            getattr(question, 'answer_ids', None) or 
            getattr(question, 'option_ids', None) or 
            getattr(question, 'suggested_answer_ids', None) or 
            []
        )
        
        if not answer_records:
            continue
        
        # Find correct answers
        correct_answers = answer_records.filtered(lambda a: getattr(a, 'is_correct', False))
        
        # Simulate realistic performance (80% correct)
        is_correct = random.random() < 0.8
        
        if is_correct:
            selected_answers = correct_answers[:1] if correct_answers else answer_records[:1]
            correct_count += 1
        else:
            wrong_answers = answer_records - correct_answers
            selected_answers = wrong_answers[:1] if wrong_answers else answer_records[:1]
        
        # Create quiz line
        quiz_line_vals = {
            'slide_partner_id': attempt.id,
            'question_id': question.id,
            'answer_ids': [(6, 0, selected_answers.ids)],
            'is_correct': is_correct,
            'score': 100.0 if is_correct else 0.0,
        }
        
        quiz_lines.append((0, 0, quiz_line_vals))
    
    if quiz_lines:
        attempt.write({'quiz_line_ids': quiz_lines})
        score = (correct_count / len(questions) * 100) if questions else 0
        print(f"✓ {slide.name}: {correct_count}/{len(questions)} ({score:.0f}%)")
        populated_count += 1
    else:
        skipped_count += 1

# Commit the changes
env.cr.commit()

print(f"\n{'='*60}")
print(f"Summary:")
print(f"  ✓ Populated: {populated_count} quiz attempts")
print(f"  ⚠ Skipped: {skipped_count} quiz attempts")
print(f"{'='*60}\n")
print("✅ Done! Refresh your browser to see the question-level data.")
