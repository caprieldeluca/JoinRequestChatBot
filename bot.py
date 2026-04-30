import asyncio
import datetime
import html
import json
import logging
import os
import sys
import traceback
import yaml
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Bot,
)
from telegram.error import RetryAfter, Forbidden, BadRequest, ChatMigrated
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    ChatJoinRequestHandler,
    Defaults,
    filters,
    MessageHandler,
    CallbackQueryHandler,
    PicklePersistence,
    CommandHandler,
    Application,
    JobQueue,
)
from typing import List

logger = logging.getLogger(__name__)

# Environment variable names.
ENV_TOKEN = "TOKEN"
ENV_CUSTOM_CONFIG = "CUSTOM_CONFIG_PATH" # Optional.

# Hardcoded (next to this file) default config path (required).
DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.yaml"

def load_configs():
    """
    Loads the Bot token and configuration variables.

    Mandatory default configuration values are loaded from 'config.yaml'
        (must be located in the same directory as 'bot.py'). These can be
        overridden by a custom YAML file specified via the 'CUSTOM_CONFIG_PATH'
        environment variable.

    All custom variables are optional. If 'CUSTOM_CONFIG_PATH' is undefined,
        only defaults are used. Custom keys not present in the default
        configuration are ignored.

    Returns:
        tuple[str, dict]:
            - Token (str) retrieved from the 'TOKEN' environment variable.
            - Configuration (dict) containing merged default and custom values.

    Raises:
        ValueError: If 'TOKEN' environment variable is missing.
        RuntimeError: If configuration files are missing, inaccessible,
            or contain invalid YAML syntax.
    """
    # Errors here cause the script to stop.
    # Prints to STDERR and STDOUT for explicit capture in the service.
    # TODO: Integrate sys outputs and bot logs.

    # Token.
    token = os.getenv(ENV_TOKEN)
    if not token:
        error_msg = "TOKEN environment variable not found."
        print(f"ERROR: {error_msg}", file=sys.stderr)
        raise ValueError(error_msg)

    # Default config.
    try:
        with open(DEFAULT_CONFIG, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except (FileNotFoundError, PermissionError, yaml.YAMLError) as e:
        exc_name = type(e).__name__
        error_msg = f"{exc_name}: {e}"
        print(f"ERROR: {error_msg}", file=sys.stderr)
        raise RuntimeError(error_msg) from e

    # Custom config.
    custom_config_path = os.getenv(ENV_CUSTOM_CONFIG)
    if custom_config_path:
        try:
            with open(custom_config_path, 'r', encoding='utf-8') as f:
                custom_config = yaml.safe_load(f) or {} # Empty custom config.
        except (FileNotFoundError, PermissionError, yaml.YAMLError) as e:
            exc_name = type(e).__name__
            error_msg = f"{exc_name}: {e}"
            print(f"ERROR: {error_msg}", file=sys.stderr)
            raise RuntimeError(error_msg) from e

        def _apply_overrides(base, overrides):
            """Helper recursive function to override config options."""
            for key, value in overrides.items():
                if key in base:
                    if isinstance(value, dict) and isinstance(base[key], dict):
                        _apply_overrides(base[key], value)
                    elif value is not None:
                        base[key] = value
                    else:
                        warn_msg = f"Configuration key '{key}' has no value in custom config. Ignored."
                        print(warn_msg, file=sys.stdout)
                else:
                    warn_msg = f"New variable name found in custom config: '{key}'. Ignored."
                    print(warn_msg, file=sys.stdout)

        _apply_overrides(config, custom_config)
    else:
        warn_msg = f"WARNING: '{ENV_CUSTOM_CONFIG}' environment variable not found, using only config defaults."
        print(warn_msg, file=sys.stdout)

    return token, config


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Finally, send the message
    await context.bot.send_message(chat_id=config["dev_chat_id"], text=message)


def create_buttons(user_id: int):
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Aceptar", callback_data=f"y_{user_id}"),
                InlineKeyboardButton("❌ Rechazar", callback_data=f"n_{user_id}"),
            ],
            [InlineKeyboardButton("🛑 Banear", callback_data=f"b_{user_id}")],
        ]
    )
    return buttons


def update_job(job_queue: JobQueue, job_name: int):
    """
    Changes the date trigger of a scheduled job.

    Params:
        job_queue: The queue of scheduled jobs.
        job_name: Name of the job to update. It is the related user_id.

    Returns:
        datetime.datetime: UTC datetime of the updated job trigger.
    """
    try:
        job = job_queue.get_jobs_by_name(str(job_name))[0]
    except IndexError:
        # this can happen after a restart. No need to worry about this.
        return

    d = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=config["expiration_minutes"])
    job.job.reschedule("date", run_date=d)
    return d


async def reject_job(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.user_id

    decline_success = False
    try:
        await context.bot.decline_chat_join_request(
            chat_id=config['main_group_id'],
            user_id=user_id
        )
        decline_success = True
    except Forbidden:
        # The account got deleted.
        pass
    except BadRequest as e:
        if e.message == "Hide_requester_missing":
            # Join request not found in main group.
            pass
        else:
            raise

    # Don't send message if decline failed
    if decline_success:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=config["expired_msg"]
            )
        except Forbidden:
            # If somebody blocks me.
            pass

    # If Key Error, user was already finished.
    # Manually check the pickle and remove their messages in approve group.
    await finish_user(
        context,
        "Join request of " + context.bot_data["user_mentions"][user_id] + " expired.",
        config["approve_group_id"],
        user_id,
        context.bot_data["last_message_to_user"][user_id],
    )


async def join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # this check tells us if the user has already pressed the chat join request button and decided to hit it again
    if context.job_queue.get_jobs_by_name(str(update.effective_user.id)):
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="No necesitas solicitar unirte nuevamente. Escribe tu mensaje y se lo enviaré a los/as admins.",
        )
        # the return is important so we don't do the things below again
        return

    # send welcome message
    try:
        await context.bot.send_message(chat_id=update.effective_user.id, text=config["welcome_msg"])
    except Forbidden:
        # The user blocked me but sent a join request.
        # TODO: Inform it in approve chat.
        pass

    # this needs to be a get_chat, because has_private_forwards is only set here
    user = await context.bot.get_chat(chat_id=update.effective_user.id)

    if user.has_private_forwards and not user.username:
        message = f"The user {user.full_name} has sent a join request, but can not be mentioned :(."
        context.bot_data["user_mentions"][user.id] = user.full_name
    else:
        if user.username:
            mention = f"@{user.username}"
        else:
            mention = f'<a href="tg://user?id={user.id}">{user.full_name}</a>'

        message = f"The user {mention} has sent a join request \\o/"
        context.bot_data["user_mentions"][user.id] = mention

    # Define (keyword) args to send message.
    kwargs = {
        "chat_id": config["approve_group_id"],
        "text": message,
        "reply_markup": create_buttons(user.id)
    }
    # Optional topic (if no falsy value provided).
    if config["requests_appr_tid"]:
        kwargs["message_thread_id"] = config["requests_appr_tid"]

    send_message = await context.bot.send_message(**kwargs)

    if user.id in context.bot_data["messages_to_edit"]:
        context.bot_data["messages_to_edit"][user.id].append(send_message.message_id)
    else:
        context.bot_data["messages_to_edit"][user.id] = [send_message.message_id]
        context.bot_data["last_message_to_user"][user.id] = send_message.message_id

    d = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=config["expiration_minutes"])
    context.job_queue.run_once(
        reject_job,
        when=d,
        user_id=user.id,
        name=str(user.id)
    )
    context.bot_data["user_expiration"][user.id] = str(d)


async def message_from_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in context.bot_data["user_mentions"]:
        # We don't know this user.
        await update.effective_message.reply_text(
            config["disconnected_msg"],
            do_quote=True
        )
        return

    elif update.effective_message.effective_attachment:
        # We don't allow attachments.
        await update.effective_message.reply_text(
            config["attachment_msg"],
            do_quote=True
        )
        return

    else:
        user_id = update.effective_user.id
        user_mention = context.bot_data["user_mentions"][user_id]

        # Define (keyword) args to send message.
        kwargs = {
            "chat_id": config["approve_group_id"],
            "text": f"{update.effective_message.text_html_urled}\n\nThis message was sent by {user_mention}",
            "reply_to_message_id": context.bot_data["last_message_to_user"][user_id],
            "reply_markup": create_buttons(user_id)
        }
        # Optional topic (if no falsy value provided).
        if config["responses_appr_tid"]:
            kwargs["message_thread_id"] = config["responses_appr_tid"]

        message = await context.bot.send_message(**kwargs)
        context.bot_data["messages_to_edit"][user_id].append(message.message_id)
        # Reply to user with a "message sent" message.
        await update.effective_message.reply_text(
            config["sent_msg"],
            do_quote=True
        )

    # kick the deadline
    d = update_job(context.job_queue, user_id)
    context.bot_data["user_expiration"][user_id] = str(d)


async def message_from_group(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_message.text.startswith("!"):
        # Message text starts with "!". Ignore.
        return

    if not update.effective_message.reply_to_message.reply_markup:
        if update.effective_message.reply_to_message.from_user.id == context.bot.id:
            await update.effective_message.reply_text(
                "Sorry, you either replied to the wrong message, "
                "or this user has been dealt with already."
            )
        return

    # we get the user id from the old reply markup
    user_id = int(
        update.effective_message.reply_to_message.reply_markup.inline_keyboard[0][0].callback_data.split("_")[1]
    )

    if user_id not in context.bot_data["user_mentions"]:
        await update.effective_message.reply_text(
            "Sorry, this user has been dealt with already."
        )
        return

    context.bot_data["last_message_to_user"][user_id] = update.effective_message.message_id

    try:
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id,
        )
    except Forbidden:
        message = await update.effective_message.reply_text(
            f"The user {context.bot_data['user_mentions'][user_id]} blocked me, "
            f"I can't send them messages anymore. I can still ban them however 😈",
            reply_markup=create_buttons(user_id),
        )
        context.bot_data["messages_to_edit"][user_id].append(message.message_id)
        return
    send_message = await update.effective_message.reply_text(
        f"Message sent to {context.bot_data['user_mentions'][user_id]}",
        reply_markup=create_buttons(user_id),
    )
    context.bot_data["messages_to_edit"][user_id].append(send_message.message_id)
    # Kick the deadline. Note than update_job returns the new datetime object.
    d = update_job(context.job_queue, user_id)
    context.bot_data["user_expiration"][user_id] = str(d)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = update.callback_query.data.split("_")
    user_id = int(data[1])
    try:
        if data[0] == "y":
            try:
                await context.bot.approve_chat_join_request(chat_id=config["main_group_id"], user_id=user_id)
            except Forbidden:
                # telegram disabled the account
                pass

            text = f"{update.effective_user.mention_html()} accepted the join request."
        elif data[0] == "n":
            try:
                await context.bot.decline_chat_join_request(chat_id=config["main_group_id"], user_id=user_id)
            except Forbidden:
                pass

            text = f"{update.effective_user.mention_html()} rejected the join request."
        else:
            try:
                await context.bot.ban_chat_member(chat_id=config["main_group_id"], user_id=user_id)
                await context.bot.decline_chat_join_request(chat_id=config["main_group_id"], user_id=user_id)
            except BadRequest as e:
                if e.message == "Participant_id_invalid":
                    # telegram was quicker and they banned the account
                    pass
            except Forbidden:
                pass

            text = f"{update.effective_user.mention_html()} banned the join request."
    except BadRequest as e:
        if e.message == "Hide_requester_missing":
            text = (
                f"Sorry {update.effective_user.mention_html()}, "
                f"but the join request was already handled by someone else :("
            )
            message_id = update.callback_query.message.message_id
            if user_id not in context.bot_data["messages_to_edit"]:
                context.bot_data["messages_to_edit"][user_id] = [message_id]
            elif message_id not in context.bot_data["messages_to_edit"][user_id]:
                context.bot_data["messages_to_edit"][user_id].append(message_id)
        else:
            raise
    try:
        context.job_queue.get_jobs_by_name(str(user_id))[0].schedule_removal()
    except IndexError:
        # this can happen after a restart. No need to worry about this.
        pass

    # If Key Error, user was already finished.
    # Manually check the pickle and remove their messages in approve group.
    await finish_user(
        context,
        text,
        update.effective_chat.id,
        user_id,
        update.callback_query.message.message_id,
        update,
    )


async def finish_user(
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    chat_id: int,
    user_id: int,
    message_id: int = None,
    update: Update = None,
):
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_to_message_id=message_id,
    )
    context.application.create_task(
        edit_buttons(context.bot, context.bot_data["messages_to_edit"][user_id]), update
    )

    # Clean bot_data.
    context.bot_data["messages_to_edit"].pop(user_id, None)
    context.bot_data["last_message_to_user"].pop(user_id, None)
    context.bot_data["user_mentions"].pop(user_id, None)
    context.bot_data["user_expiration"].pop(user_id, None)


async def edit_buttons(bot: Bot, messages_to_edit: List[int]):
    # every second we edit out a button. We wait this long, so we don't rate limit the bot
    # instead of reversed here, I should have done prepend instead of append I guess
    for message_id in reversed(messages_to_edit):
        try:
            await bot.edit_message_reply_markup(
                chat_id=config["approve_group_id"], message_id=message_id, reply_markup=None
            )
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
            await bot.edit_message_reply_markup(
                chat_id=config["approve_group_id"], message_id=message_id, reply_markup=None
            )
        await asyncio.sleep(1)


async def first_run_check(application: Application):
    """
    Do last things before start to run.

    Updates bot_data. Schedules reject_jobs.
    """
    b_d = application.bot_data

    # Create empty bot_data items if there are not previous ones.
    b_d.setdefault("messages_to_edit", {})
    b_d.setdefault("user_mentions", {})
    b_d.setdefault("last_message_to_user", {})
    b_d.setdefault("user_expiration", {})

    # Restore scheduled reject jobs.
    i = 0 # Expired index.
    for key, value in b_d["user_expiration"].items():
        user_id = key
        d = datetime.datetime.fromisoformat(value)
        now = datetime.datetime.now(datetime.UTC)
        if d < now:
            # Expired. Reschedule to one minute + i seconds from now
            d = now + datetime.timedelta(seconds=60+i)
            i += 1

        application.job_queue.run_once(
            reject_job,
            when=d,
            user_id=user_id,
            name=str(user_id)
        )


if __name__ == "__main__":
    token, config = load_configs()

    # TODO: Handle log and persistence files system errors.
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.ERROR,
        filename=config["log_path"],
    )
    persistence = PicklePersistence(filepath=config["state_path"])

    defaults = Defaults(parse_mode="html")
    application = (
        ApplicationBuilder()
        .token(token)
        .defaults(defaults)
        .persistence(persistence)
        .post_init(first_run_check)
        .build()
    )

    application.add_handler(ChatJoinRequestHandler(join_request))
    application.add_handler(
        MessageHandler(
            filters.Chat(config["approve_group_id"]) & filters.REPLY & filters.TEXT,
            message_from_group,
        )
    )
    application.add_handler(
        MessageHandler(filters.ChatType.PRIVATE, message_from_private)
    )
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)
    application.run_polling(
        allowed_updates=[
            Update.MESSAGE,
            Update.CHAT_JOIN_REQUEST,
            Update.CALLBACK_QUERY,
        ]
    )
