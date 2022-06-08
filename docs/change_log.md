# Change Log

## Tag Profile with Store at Enrollment

### Previous Scenario

When checkout a course/section from consumer API, student/purchaser profiles were created by the following
1. From the very beginning, purchaser profile (Profile Model) will be created
2. Create cart with purchaser profile
   1. If payment > 0, request payment gateway with necessary info to authorize payment amount. Return to webhooks with response
   2. If success, tag purchaser profile with store (ProfileStore Model)
3. Create course enrollment with students profile (Profile Model)
4. Place an enrollment request to partner to their given url. Return to webhooks with response
5. If partner enrollment is successful
   1. Create student profile (StudentProfile Model) with school_student_id 
   2. If payment > 0, request payment gateway to capture payment

### Change Scenario
1. From the very beginning, purchaser profile (Profile Model) will be created
2. Create cart with purchaser profile
   1. If payment > 0, request payment gateway with necessary info to authorize payment amount. Return to webhooks with response
3. Create course enrollment with students profile (Profile Model)
4. Place an enrollment request to partner to their given url. Return to webhooks with response
5. If partner enrollment is successful
   1. Create student profile (StudentProfile Model) with school_student_id
   2. Tag student profile with store (ProfileStore Model)
   3. Tag purchaser profile with store (ProfileStore Model)
   4. If payment > 0, request payment gateway to capture payment