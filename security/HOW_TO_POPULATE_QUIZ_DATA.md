# How to Populate Question-Level Quiz Data

## Current Situation

Your existing quiz attempts show **"Passed (No details)"** because they were completed before the question-level tracking feature was implemented. The system **is now ready** to capture question-level data for all **new** quiz attempts.

## Solution Options

### Option 1: Take a New Quiz (Recommended - Easiest)

**This is the best way to see the feature in action with real data.**

1. Have a guard log into the mobile app
2. Take any quiz through the mobile interface
3. The system will automatically capture all question-level data
4. View the results in the enrollment form

**Result**: You'll see actual question responses with correct/incorrect status for each question.

---

### Option 2: Populate Test Data for Existing Quizzes

If you want to see the feature work with your existing quiz attempts, you can populate them with simulated test data.

#### Steps:

1. **Stop Odoo**:
   ```bash
   cd /home/azureuser/security
   sudo docker-compose stop odoo
   ```

2. **Run the population script**:
   ```bash
   sudo docker-compose run --rm odoo odoo shell -c /etc/odoo/odoo.conf -d security
   ```

3. **In the Odoo shell, paste this code**:
   ```python
   import random

   # Find quiz attempts without question details
   quiz_attempts = env['slide.slide.partner'].search([
       ('slide_id.slide_category', '=', 'quiz'),
       ('completed', '=', True),
       ('quiz_line_ids', '=', False)
   ], limit=100)

   print(f"Found {len(quiz_attempts)} quiz attempts to populate")

   populated_count = 0

   for attempt in quiz_attempts:
       slide = attempt.slide_id
       questions = slide.question_ids if hasattr(slide, 'question_ids') else []
       
       if not questions:
           continue
       
       quiz_lines = []
       correct_count = 0
       
       for question in questions:
           answer_records = (
               getattr(question, 'answer_ids', None) or 
               getattr(question, 'option_ids', None) or 
               getattr(question, 'suggested_answer_ids', None) or 
               []
           )
           
           if not answer_records:
               continue
           
           correct_answers = answer_records.filtered(lambda a: getattr(a, 'is_correct', False))
           is_correct = random.random() < 0.8  # 80% pass rate
           
           if is_correct:
               selected_answers = correct_answers[:1] if correct_answers else answer_records[:1]
               correct_count += 1
           else:
               wrong_answers = answer_records - correct_answers
               selected_answers = wrong_answers[:1] if wrong_answers else answer_records[:1]
           
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

   env.cr.commit()
   print(f"\n✅ Populated {populated_count} quiz attempts")
   ```

4. **Exit the shell**:
   ```python
   exit()
   ```

5. **Start Odoo**:
   ```bash
   sudo docker-compose start odoo
   ```

6. **Refresh your browser** and check the quiz responses!

---

## What You'll See After Population

### Before:
- Quiz Responses tab shows: "Passed (No details)"
- Quiz Attempts button is empty
- No individual question data

### After:
- Quiz Responses tab shows: "3/5" (3 correct out of 5 questions)
- Quiz Attempts button shows count
- Individual questions visible with ✓ or ✗ for each

---

## Understanding the Data

### For Test Data (Option 2):
- **Simulated**: The answers are randomly generated (80% correct rate)
- **Purpose**: To demonstrate the feature functionality
- **Not Real**: These aren't the actual answers the guards selected

### For New Quizzes (Option 1):
- **Real**: Actual answers selected by guards
- **Accurate**: True representation of guard knowledge
- **Trackable**: Complete audit trail of quiz performance

---

## Troubleshooting

### "No quiz attempts found"
**Cause**: All quizzes already have question data, or quizzes have no questions configured.
**Solution**: Check that your quiz slides actually have questions attached.

### Script shows errors
**Cause**: Database connection issue or permission problem.
**Solution**: Make sure Odoo is stopped before running the shell command.

### Still showing "Passed (No details)"
**Cause**: Browser cache or the specific quiz has no questions.
**Solution**: 
1. Hard refresh your browser (Ctrl+F5)
2. Check if the quiz slide has questions configured
3. Verify the script ran successfully

---

## Recommendation

**I strongly recommend Option 1** (taking a new quiz) because:
- ✅ Shows real, actual data
- ✅ No manual intervention needed
- ✅ Demonstrates the feature as it will work in production
- ✅ No risk of data corruption
- ✅ Easier and faster

**Use Option 2 only if**:
- You need to demonstrate the feature immediately
- You don't have time to take a real quiz
- You want to see how the UI looks with populated data

---

## Next Steps

1. **Choose your option** (1 or 2)
2. **Follow the steps** above
3. **Refresh your browser**
4. **Navigate to**: Training → eLearning Enrollments
5. **Open any enrollment**
6. **Click "Quiz Attempts"** smart button
7. **See the question-level data!**

---

## Questions?

- Check: `QUESTION_LEVEL_DATA_IMPLEMENTATION.md` for full documentation
- Check: `QUIZ_DATA_QUICK_GUIDE.md` for quick reference
- The feature is **fully functional** and ready to use!
