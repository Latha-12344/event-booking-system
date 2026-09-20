Design and implement the backend APIs for an Event Booking System
AI tools are encouraged. Document ALL your design decisions in the README file. Do spend some time initially to plan out how you will do it. Manage your time accordingly. Deploy it online. You can use Vercel, Netlify, Cloudflare, Heroku, Render, etc.

Support two types of users:

Event Organizers
Customers
Event Organizers manage events, while Customers browse events and book tickets. API access must be controlled based on user roles.

Implement background tasks using any job queue or async processing mechanism of your choice.

Background Task 1: Booking Confirmation
Triggered when a customer successfully books tickets

Sends a real booking confirmation email (a console log / print statement indicating the email action is NOT sufficient)

Background Task 2: Event Update Notification
Triggered when an event is updated

Notifies all customers who have booked tickets for that event (a console log / print statement indicating notification is NOT sufficient)

Performance
Run a stress scenario on your APIs and find out how many users can it handle simultaneously for booking an event.

Record one video showing the demo of what you’ve built by making API calls to your deployed link. Use Loom or any other tool to record yourself and your computer screen. Minimum duration should be 2 minutes, maximum 5 minutes and the ideal length would be around 3-4 minutes. IMPORTANT NOTE: You have to show your face as well. Make sure to speak in English while showing the demo. In the demo video, show 3 things (ALL are mandatory!):

The constraints (# of concurrent users / bookings / event updates) at which performance degrades in the initial LLM implementation (don't just tell, actually show the breaking point after which more requests get dropped)
Talk about how you can optimize this (feel free to search and read more on this, most of the time is meant for this exploration/experimentation)
Show the final constraints till which you were able to optimize (this is the delta that you bring to the table)