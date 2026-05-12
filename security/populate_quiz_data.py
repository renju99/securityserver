#!/usr/bin/env python3
"""
Populate Question-Level Quiz Data for Testing

This script creates sample question-level responses for existing quiz attempts
that show "Passed (No details)" so you can see the question-level tracking feature.

Usage:
    Run this from Odoo shell:
    sudo docker-compose exec -T odoo_security odoo shell -c /etc/odoo/odoo.conf -d security < populate_quiz_data.py
"""

import random

# Get environment
env = self.env

print("=" * 60)
print("Populating Question-Level Quiz Data")
print("=" * 60)

# Find quiz attempts without detailed responses
quiz_attempts = env['slide.slide.partner'].search([
    ('slide_id.slide_category', '=', 'quiz'),
    ('completed', '=', True),
    ('quiz_line_ids', '=', False)  # No question-level data
])

print(f"\nFound {len(quiz_attempts)} quiz attempts without question details")

if not quiz_attempts:
    print("\n✓ All quiz attempts already have question-level data!")
    print("  Try taking a new quiz through the mobile app to see live data capture.")
    exit()

populated_count = 0
skipped_count = 0

for attempt in quiz_attempts:
    slide = attempt.slide_id
    
    # Get questions for this quiz
    questions = slide.question_ids if hasattr(slide, 'question_ids') else []
    
    if not questions:
        print(f"\n⚠ Skipping {slide.name} - No questions found")
        skipped_count += 1
        continue
    
    print(f"\n📝 Processing: {slide.name}")
    print(f"   Questions: {len(questions)}")
    print(f"   Guard: {attempt.partner_id.name}")
    
    # Create question responses
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
        
        # Find correct answer(s)
        correct_answers = answer_records.filtered(lambda a: getattr(a, 'is_correct', False))
        
        # Simulate a realistic pass rate (70-90% correct)
        is_correct = random.random() < 0.8  # 80% chance of correct answer
        
        if is_correct:
            # Select correct answer
            selected_answers = correct_answers[:1] if correct_answers else answer_records[:1]
            correct_count += 1
        else:
            # Select wrong answer
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
        # Update the quiz attempt with question responses
        attempt.write({
            'quiz_line_ids': quiz_lines
        })
        
        score = (correct_count / len(questions) * 100) if questions else 0
        print(f"   ✓ Created {len(quiz_lines)} question responses")
        print(f"   Score: {correct_count}/{len(questions)} ({score:.1f}%)")
        populated_count += 1
    else:
        print(f"   ⚠ No valid questions to populate")
        skipped_count += 1

print("\n" + "=" * 60)
print("Summary")
print("=" * 60)
print(f"✓ Populated: {populated_count} quiz attempts")
print(f"⚠ Skipped: {skipped_count} quiz attempts (no questions)")
print(f"📊 Total processed: {len(quiz_attempts)}")
print("\n✅ Done! Refresh your browser to see the question-level data.")
print("=" * 60)
