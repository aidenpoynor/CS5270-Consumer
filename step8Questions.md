1. Why is it possible that Update and Delete Widget Requests may fail, even when you are running just one Consumer?

Standard SQS queues guarantee at-least-once delivery, but they do not guarantee ordering, and a newly sent message can take a short time to become visible to receive calls. So a Consumer can receive an Update or Delete for a widget before it has received the Create for that same widget. When the Update or Delete runs, the target object does not exist yet, so the operation fails. Receiving messages in batches of up to 10 makes this more likely, because requests in the same batch can be processed out of their original order.

2. How would this possible behavior impact the design of distributed applications that use queues?

Because messages can arrive out of order and be delivered more than once, applications that use queues have to be designed to delete from the queue only after it has been processed successfully. If it fails, it needs to requeue and try again later, requeuing until after the target object is created.
