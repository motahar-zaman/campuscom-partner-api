# Change Log

## Tag Profile with Store at Enrollment
### Change Date: 7 June 2022

## Reason behind the changes
We didn't tag profile with store if payment = 0. for this reason we didn't get store's profile for free courses. Now we resolve it.

### Previous Scenario

When checkout a course/section from consumer API, student/purchaser profiles were created by the following
1. From the initiate_payment(checkout api) method, create purchaser profile (Profile Model) first
2. Create cart with purchaser profile, then
   1. If payment > 0, request payment gateway with necessary info to authorize payment amount. Return to webhooks with response
   2. If success, tag purchaser profile with store (ProfileStore Model)
3. Create course enrollment with students profile (Profile Model)
4. Place an enrollment request to partner to their given url. Return to webhooks with response
5. If partner enrollment is successful
   1. Create student profile (StudentProfile Model) with school_student_id 
   2. If payment > 0, request payment gateway to capture payment

### Change Scenario
1. Move step 2(ii) to step 5.
2. In step 5, add
   1. Tag student profile with store (ProfileStore Model)
   2. Tag purchaser profile with store (ProfileStore Model)