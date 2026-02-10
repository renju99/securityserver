# Question-Level Quiz Data - Quick Reference Guide

## 🎯 What's New?

You can now view **individual question responses** for every quiz attempt, showing exactly which questions were answered correctly or incorrectly.

## 📊 How to Access

### Option 1: Smart Button (Fastest)
1. Open any **Training Enrollment** record
2. Click the **"Quiz Attempts"** smart button (top right)
3. See all question-level responses in one view

### Option 2: Quiz Responses Tab
1. Open any **Training Enrollment** record
2. Go to **"Quiz Responses"** tab
3. Click on a quiz attempt
4. Scroll to **"Individual Question Responses"**

### Option 3: From Guard Profile
1. **Guards → Guard Profiles**
2. Select a guard
3. **"eLearning Training"** tab
4. Click on an enrollment
5. Use Option 1 or 2 above

## 🎨 Visual Indicators

| Indicator | Meaning |
|-----------|---------|
| 🟢 Green Row | Correct answer |
| 🔴 Red Row | Incorrect answer |
| ✅ "Correct" Badge | Question answered correctly |
| ❌ "Incorrect" Badge | Question answered incorrectly |
| 🟢 "Passed" Badge | Quiz passed |
| 🔴 "Failed" Badge | Quiz failed |

## 📋 What You Can See

For each question:
- ✅ Question text
- ✅ Answer(s) selected by the guard
- ✅ Whether it was correct or incorrect
- ✅ Points earned
- ✅ Date/time of attempt

For each quiz:
- ✅ Quiz name
- ✅ Score (e.g., "3/5" = 3 correct out of 5)
- ✅ Percentage score
- ✅ Pass/fail status
- ✅ Attempt date

For each enrollment:
- ✅ Overall course score
- ✅ "Correct" or "Not Correct" status
- ✅ Certification status
- ✅ All quiz attempts

## 💡 Use Cases

### For Supervisors
- Identify which guards struggle with specific topics
- Find questions that many guards get wrong
- Verify compliance with training requirements
- Generate detailed performance reports

### For Managers
- Track training effectiveness
- Identify areas for course improvement
- Monitor guard competency levels
- Audit training completion

### For Guards (Portal)
- Review their own quiz performance
- See which questions they got wrong
- Track their learning progress
- Prepare for retakes

## 🔍 Example Scenarios

### Scenario 1: Check a Guard's Quiz Performance
```
1. Guards → Guard Profiles → Select "John Smith"
2. eLearning Training tab
3. Find "Fire Safety" enrollment
4. Click "Quiz Attempts" button
5. See all questions John answered across all Fire Safety quizzes
```

### Scenario 2: Find Difficult Questions
```
1. Training → eLearning Enrollments
2. Filter by course (e.g., "First Aid")
3. Open multiple enrollments
4. Compare which questions are frequently wrong
5. Update course content to address weak areas
```

### Scenario 3: Verify Compliance
```
1. Open guard enrollment
2. Quiz Responses tab
3. Verify all mandatory quiz questions were answered
4. Confirm correct answers for critical safety questions
5. Export/print for audit trail
```

## 📱 Mobile Access

Guards can view their own quiz responses through the portal:
- Login to guard portal
- My Training section
- View course details
- See quiz results and individual questions

## 🔒 Security

| Role | Can View |
|------|----------|
| Guards | Own responses only |
| Supervisors | Guards they supervise |
| Managers | All guards |
| Admins | Everything |

## ⚡ Quick Tips

1. **Smart Button is Fastest**: Use the "Quiz Attempts" button for quick access
2. **Filter by Status**: Use list filters to find failed quizzes
3. **Export Data**: Use Odoo's export feature for reporting
4. **Color Coding**: Green = good, Red = needs attention
5. **Historical Data**: All past quiz attempts are preserved

## 🆘 Troubleshooting

**Q: I don't see the "Quiz Attempts" button**
A: The button only appears if the guard has taken quizzes. Check the Quiz Responses tab.

**Q: Quiz shows "No details available"**
A: This quiz was completed before the feature was enabled. New attempts will show details.

**Q: Can I see which answer was correct?**
A: Currently shows if the guard's answer was correct/incorrect. The correct answer itself is not displayed to prevent cheating.

**Q: Can guards retake quizzes?**
A: Yes, if the course allows retakes. Each attempt is tracked separately.

## 📞 Support

For questions or issues:
- Check the full documentation: `QUESTION_LEVEL_DATA_IMPLEMENTATION.md`
- Contact your system administrator
- Email: mails4ranjith@gmail.com

---

**Last Updated**: February 6, 2026
**Version**: 18.0.1.0.9
**Module**: guardpro
