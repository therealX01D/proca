import asyncio
from processor import ProcessEngine, EventStore, ProcessDefinitionLoader, Context, CommandStep, ValidationStep

async def create_user(ctx):
    return {"id": "user-123", "email": ctx.data["email"]}

async def send_welcome(ctx):
    # pretend send mail
    return {"sent": True}

async def main():
    event_store = EventStore()
    engine = ProcessEngine(event_store)

    process_def = {
        "name": "user_registration",
        "steps": [
            {"name": "validate_email", "type": "validation", "dependencies": []},
            {"name": "create_user", "type": "command", "dependencies": ["validate_email"]},
            {"name": "send_welcome_email", "type": "side_effect", "dependencies": ["create_user"]}
        ]
    }

    ctx = Context()
    ctx.data = {"email": "user@example.com", "name": "John Doe"}

    # Build custom steps and run engine directly (recommended vs using minimal factory)
    from processor.steps.validation import ValidationStep
    from processor.steps.command import CommandStep
    from processor.steps.query import QueryStep

    steps = [
        ValidationStep("validate_email", lambda ctx: "@" in ctx.data.get("email", "")),
        CommandStep("create_user", create_user, dependencies=["validate_email"]),
        CommandStep("send_welcome_email", send_welcome, dependencies=["create_user"])
    ]

    # bypass engine factory for demo: monkeypatch engine._build_steps_from_config
    engine._build_steps_from_config = lambda cfg: steps
    res_ctx = await engine.execute_process(process_def, ctx)
    print(res_ctx.data)
    events = await event_store.get_process_history(res_ctx.process_id)
    print(len(events), "events")

if __name__ == "__main__":
    asyncio.run(main())
