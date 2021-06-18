import re
import json
import logging
import traceback
from time import sleep

import telebot
from telebot import types

from utils import user_dict, UserDict, RefreshToken

from az.az_token import Token
from az.az_sub import Subscription
from az.az_rg import ResourceGroup
from az.az_nic import Network
from az.az_vm import VirtualMachine
from az.az_config import VM_LOCATIONS, VM_SIZES, VM_OS_INFOS

config = json.load(open('config.json', 'r', encoding='utf-8'))
BOT_TOKEN = config['BOT']['TOKEN']
BOT_ADMINS = config['BOT']['ADMINS']
BOT_NAME = config['BOT']['NAME']

bot = telebot.TeleBot(BOT_TOKEN)


@bot.message_handler(content_types=['text'])
def handle_text(m):
    try:
        logger.info(m)

        if m.from_user.id not in BOT_ADMINS:
            return

        start(m)
    except Exception as e:
        traceback.print_exc()
        handle_exception(e, m)


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        logger.info(call)

        if call.from_user.id not in BOT_ADMINS or \
                len(call.data.split(':')) != 3:
            return

        action = call.data.split(':')[0]
        sub_action = call.data.split(':')[1]
        value = call.data.split(':')[2]

        if action == 'aa':
            add_account(call)

        elif action == 'ma':
            if sub_action == '':
                list_accounts(call, '管理账号', action, 'ss')
            elif sub_action == 'ss':
                show_account_sub(call, value)
            elif sub_action == 'rm':
                remove_account(call, value)

        elif action == 'cvm':
            if sub_action == '':
                list_accounts(call, '创建实例', action, 'ce')
            elif sub_action == 'ce':
                set_refresh_token_list_sub(call, value, create_vm_set_subscription_id_list_size)
            elif sub_action == 'cs':
                create_vm_set_subscription_id_list_size(call, value)
            elif sub_action == 'csize':
                create_vm_set_size_list_os(call, value)
            elif sub_action == 'cos':
                create_vm_set_os_list_location(call, value)
            elif sub_action == 'cl':
                create_vm_set_location_confirm_create(call, value)
            elif sub_action == 'ok':
                create_vm(call)
            elif sub_action == 'cancel':
                edit_cancel(call)

        elif action == 'mvm':
            if sub_action == '':
                list_accounts(call, '管理实例', action, 'ce')
            elif sub_action == 'ce':
                set_refresh_token_list_sub(call, value, manage_vm_set_subscription_id_list_vm)
            elif sub_action == 'cs':
                manage_vm_set_subscription_id_list_vm(call, value)
            elif sub_action == 'gvm':
                get_vm(call, value)
            elif sub_action == 'ip':
                change_vm_ip(call, value)
            elif sub_action == 'del':
                delete_vm(call, value)

    except Exception as e:
        traceback.print_exc()
        handle_exception(e, call)


def handle_exception(e, d):
    bot.send_message(
        text=f'出错啦\n<code>{e}</code>',
        chat_id=d.from_user.id,
        parse_mode='HTML'
    )
    start(d)


def start(m):
    user_dict[m.from_user.id] = UserDict()

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(text='添加账号', callback_data='aa::'),
        types.InlineKeyboardButton(text='管理账号', callback_data='ma::'),
        types.InlineKeyboardButton(text='创建实例', callback_data='cvm::'),
        types.InlineKeyboardButton(text='管理实例', callback_data='mvm::')
    )
    bot.send_message(
        text=f'<b>欢迎使用 <a href="https://github.com/zayabighead/azure-helper-bot">{BOT_NAME}</a></b>\n'
             f'你可以管理 Azure 账号，创建实例，更换 IP 等\n\n'
             f'请选择你要进行的操作：',
        chat_id=m.from_user.id,
        parse_mode='HTML',
        reply_markup=markup
    )


def edit_cancel(call):
    bot.edit_message_text(
        text='已取消',
        chat_id=call.from_user.id,
        message_id=call.message.message_id
    )


def add_account(call):
    msg = bot.edit_message_text(
        text='正在进行 <b>添加账号</b>\n\n'
             '请打开 '
             '<a href="https://portal.azure.com/#blade/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/Overview">此链接</a>'
             ' ，登录你要添加的 Azure 账号，找到页面上显示的 <b>租户 (Tenant) ID</b> 并回复'
             '<a href="https://i.loli.net/2020/08/12/KIeRQFLc1q9ZrEu.png">：</a>',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )
    bot.register_next_step_handler(msg, add_account_get_tenant_id)


def add_account_get_tenant_id(m):
    try:
        tenant_id = re.search(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', m.text).group()

        az_token = Token(tenant_id)
        user_code_info = az_token.get_user_code_info()

        msg = bot.send_message(
            text='租户 (Tenant) ID 获取成功\n\n'
                 '请打开 '
                 f'<a href="{user_code_info["verification_url"]}">此链接</a>'
                 f' ，输入授权码 <code>{user_code_info["user_code"]}</code> '
                 f'并登录刚才的 Azure 账号，授权码将在 {user_code_info["expires_in"]} 秒后过期，如已登录请等待刷新...',
            chat_id=m.from_user.id,
            parse_mode='HTML'
        )

        sleep(5)

        token = az_token.get(user_code_info)

        if token['tenantId'] == tenant_id:
            t = f'<code>{token["userId"]}</code> 添加成功'
            RefreshToken().save(token["userId"], token['refreshToken'])
            start(m)

        else:
            t = '账号添加失败，租户 (Tenant) ID 不一致'

        bot.edit_message_text(
            text=t,
            chat_id=m.from_user.id,
            message_id=msg.message_id,
            parse_mode='HTML'
        )

    except AttributeError:
        bot.send_message(
            text='租户 (Tenant) ID 无效',
            chat_id=m.from_user.id
        )
    except Exception as e:
        handle_exception(e, m)


def list_accounts(call, action_text, action, sub_cation):
    emails = RefreshToken().list()

    markup = types.InlineKeyboardMarkup(row_width=1)
    if emails:
        for email in emails:
            markup.add(
                types.InlineKeyboardButton(text=email, callback_data=f'{action}:{sub_cation}:{email}')
            )

        t = f'正在进行 <b>{action_text}</b>\n\n' \
            '请选择 Azure 账号：'
    else:
        t = '你还没有添加 Azure 账号'

    bot.edit_message_text(
        text=t,
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode='HTML'
    )


def show_account_sub(call, email):
    t = f'已选择 <code>{email}</code>\n\n'
    bot.edit_message_text(
        text=t + '获取账号订阅中...',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )

    refresh_token = RefreshToken().get(email)
    az_sub = Subscription(refresh_token)
    subs = az_sub.list()
    for sub in subs:
        t += f'订阅名称: <code>{sub["display_name"]}</code>\n' \
             f'订阅状态: <code>{sub["state"]}</code>\n\n'

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text='移除账号', callback_data='ma:rm:' + email))
    bot.edit_message_text(
        text=t,
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode='HTML'
    )


def remove_account(call, email):
    RefreshToken().remove(email)
    bot.edit_message_text(
        text=f'{email} 已移除',
        chat_id=call.from_user.id,
        message_id=call.message.message_id
    )


def set_refresh_token_list_sub(call, email, next_step):
    bot.edit_message_text(
        text=f'已选择 <code>{email}</code>\n\n'
             '获取账号订阅中...',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )

    refresh_token = RefreshToken().get(email)

    user_dict[call.from_user.id].email = email
    user_dict[call.from_user.id].refresh_token = refresh_token

    az_sub = Subscription(refresh_token)
    subs = az_sub.list()

    if subs[0]['state'] == 'Enabled':
        next_step(call, subs[0]['subscription_id'])
        return

    t = f'<code>{email}</code> 下没有可用订阅'
    markup = types.InlineKeyboardMarkup(row_width=1)

    bot.edit_message_text(
        text=t,
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode='HTML'
    )


def create_vm_set_subscription_id_list_size(call, subscription_id):
    user_dict[call.from_user.id].subscription_id = subscription_id

    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for size in VM_SIZES:
        buttons.append(
            types.InlineKeyboardButton(
                text=size,
                callback_data='cvm:csize:' + size
            )
        )
    markup.add(*buttons)

    bot.edit_message_text(
        text='正在进行 <b>创建实例</b>\n\n'
             '请选择实例规格:\n',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode='HTML'
    )


def create_vm_set_size_list_os(call, size):
    user_dict[call.from_user.id].size = VM_SIZES[size]

    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for os in VM_OS_INFOS:
        buttons.append(
            types.InlineKeyboardButton(
                text=os,
                callback_data='cvm:cos:' + os
            )
        )

    markup.add(*buttons)

    bot.edit_message_text(
        text='正在进行 <b>创建实例</b>\n\n'
             f'已选择规格: <code>{size}</code>\n'
             '请选择镜像:',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode='HTML'
    )


def create_vm_set_os_list_location(call, os):
    user_dict[call.from_user.id].os_info = VM_OS_INFOS[os]

    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for location in VM_LOCATIONS:
        buttons.append(
            types.InlineKeyboardButton(
                text=location,
                callback_data='cvm:cl:' + location
            )
        )

    markup.add(*buttons)

    bot.edit_message_text(
        text='正在进行 <b>创建实例</b>\n\n'
             f'已选择规格: <code>{user_dict[call.from_user.id].size}</code>\n'
             f'已选择镜像: <code>{os}</code>\n'
             '请选择地区:',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode='HTML'
    )


def create_vm_set_location_confirm_create(call, location):
    user_dict[call.from_user.id].location = VM_LOCATIONS[location]

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(text='确认', callback_data='cvm:ok:'),
        types.InlineKeyboardButton(text='取消', callback_data='cvm:cancel:')
    )
    bot.edit_message_text(
        text='正在进行 <b>创建实例</b>\n\n'
             f'已选择规格: <code>{user_dict[call.from_user.id].size}</code>\n'
             f'已选择镜像: <code>{user_dict[call.from_user.id].os_info["os"]}</code>\n'
             f'已选择地区: <code>{location}</code>\n'
             '确认创建实例 ?',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode='HTML'
    )


def create_vm(call):
    bot.edit_message_text(
        text='正在进行 <b>创建实例</b>\n\n'
             '创建资源组...',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )

    refresh_token = user_dict[call.from_user.id].refresh_token
    subscription_id = user_dict[call.from_user.id].subscription_id
    size = user_dict[call.from_user.id].size
    os_info = user_dict[call.from_user.id].os_info
    location = user_dict[call.from_user.id].location

    az_rg = ResourceGroup(refresh_token, subscription_id)
    rgn = az_rg.create(location=location)

    bot.edit_message_text(
        text='正在进行 <b>创建实例</b>\n\n'
             '创建虚拟网络..',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )
    az_nic = Network(refresh_token, subscription_id, rgn)
    az_nic.create_virtual_network(location)
    subnet_id = az_nic.create_subnet()

    bot.edit_message_text(
        text='正在进行 <b>创建实例</b>\n\n'
             '分配动态 IP...',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )
    public_ip_id = az_nic.create_public_ip(location)

    bot.edit_message_text(
        text='正在进行 <b>创建实例</b>\n\n'
             '创建安全组...',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )
    nsg_id = az_nic.create_network_security_group(location)
    az_nic.security_rules_allow_all()

    bot.edit_message_text(
        text='正在进行 <b>创建实例</b>\n\n'
             '更新网络接口...',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )
    nic_id = az_nic.create_or_update_network_interface_client(subnet_id, nsg_id, location, public_ip_id)

    bot.edit_message_text(
        text='正在进行 <b>创建实例</b>\n\n'
             '部署实例中........\n',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )
    az_vm = VirtualMachine(refresh_token, subscription_id, rgn)
    vm_info = az_vm.create(size, os_info, location, nic_id)
    public_ip = az_nic.get_public_ip()
    vm_info.update({
        'ip': public_ip
    })

    bot.edit_message_text(
        text='正在进行 <b>创建实例</b>\n\n'
             '创建实例完成\n'
             f'名称: <code>{vm_info["vm_name"]}</code>\n'
             f'IP: <code>{vm_info["ip"]}</code>\n'
             f'用户名: <code>{vm_info["username"]}</code>\n'
             f'密码: <code>{vm_info["password"]}</code>\n'
             f'镜像: <code>{vm_info["os"]}</code>\n'
             f'规格: <code>{vm_info["size"]}</code>\n'
             f'地区: <code>{vm_info["location"]}</code>\n'
             f'创建时间: <code>{vm_info["time"]}</code>\n',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )


def manage_vm_set_subscription_id_list_vm(call, subscription_id):
    user_dict[call.from_user.id].subscription_id = subscription_id
    refresh_token = user_dict[call.from_user.id].refresh_token
    email = user_dict[call.from_user.id].email

    bot.edit_message_text(
        text=f'已选择 <code>{email}</code>\n\n'
             '获取实例中...',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )

    az_vm = VirtualMachine(refresh_token, subscription_id)
    vms = az_vm.list()

    t = f'已选择 <code>{email}</code>\n\n' \
        '没有实例'
    markup = types.InlineKeyboardMarkup(row_width=1)
    if vms:
        t = '正在进行 <b>管理实例</b>\n' \
            '请选择实例:'
        for vm in vms:
            markup.add(
                types.InlineKeyboardButton(text=vm['name'], callback_data='mvm:gvm:' + vm['name'])
            )

    bot.edit_message_text(
        text=t,
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode='HTML'
    )


def get_vm(call, vm_name):
    refresh_token = user_dict[call.from_user.id].refresh_token
    subscription_id = user_dict[call.from_user.id].subscription_id

    bot.edit_message_text(
        text='正在进行 <b>管理实例</b>\n\n'
             f'获取实例 <code>{vm_name}</code> 中...',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )

    vm_info = {}

    az_vm = VirtualMachine(refresh_token, subscription_id, vm_name.replace('-vm', '-rg'))
    vms = az_vm.list()
    for vm in vms:
        if vm['name'] == vm_name:
            vm_info = vm
            break

    vm_instance_view = az_vm.instance_view()

    az_nic = Network(refresh_token, subscription_id, vm_name.replace('-vm', '-rg'))
    public_ip = az_nic.get_public_ip()

    try:
        vm_info.update({
            'os': vm_instance_view.os_name + ' ' + vm_instance_view.os_version,
            'status': vm_instance_view.statuses[1].display_status,
            'ip': public_ip
        })
    except TypeError:
        bot.edit_message_text(
            text='获取实例信息失败， 可能在创建或开机或删除过程中，请稍后再试',
            chat_id=call.from_user.id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(text='更换 IP', callback_data='mvm:ip:' + vm_name),
        types.InlineKeyboardButton(text='删除实例', callback_data='mvm:del:' + vm_name),
    )
    bot.edit_message_text(
        text='正在进行 <b>管理实例</b>\n\n'
             f'实例信息:\n'
             f'名称: <code>{vm_info["name"]}</code>\n'
             f'IP: <code>{vm_info["ip"]}</code>\n'
             f'用户名: <code>{vm_info["os_profile"]["admin_username"]}</code>\n'
             f'镜像: <code>{vm_info["os"]}</code>\n'
             f'规格: <code>{vm_info["hardware_profile"]["vm_size"]}</code>\n'
             f'地区: <code>{vm_info["location"]}</code>\n'
             f'状态: <code>{vm_info["status"]}</code>\n\n'
             f'请选择操作:',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        reply_markup=markup,
        parse_mode='HTML'
    )


def change_vm_ip(call, vm_name):
    refresh_token = user_dict[call.from_user.id].refresh_token
    subscription_id = user_dict[call.from_user.id].subscription_id

    bot.edit_message_text(
        text='正在进行 <b>管理实例</b>\n\n'
             f'更换实例 <code>{vm_name}</code> IP 中...',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )

    az_nic = Network(refresh_token, subscription_id, vm_name.replace('-vm', '-rg'))
    nic = az_nic.get_network_interface_client()
    public_ip_id = nic.ip_configurations[0].public_ip_address.id

    az_nic.create_or_update_network_interface_client(
        subnet_id=nic.ip_configurations[0].subnet.id,
        nsg_id=nic.network_security_group.id,
        location=nic.location,
        public_ip_id=None
    )

    az_nic.create_or_update_network_interface_client(
        subnet_id=nic.ip_configurations[0].subnet.id,
        nsg_id=nic.network_security_group.id,
        location=nic.location,
        public_ip_id=public_ip_id
    )

    get_vm(call, vm_name)


def delete_vm(call, vm_name):
    refresh_token = user_dict[call.from_user.id].refresh_token
    subscription_id = user_dict[call.from_user.id].subscription_id

    bot.edit_message_text(
        text='正在进行 <b>管理 VM</b>\n\n'
             f'删除实例 <code>{vm_name}</code> 及其资源组中...',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )

    az_rg = ResourceGroup(refresh_token, subscription_id)
    az_rg.delete(vm_name.replace('-vm', '-rg'))

    bot.edit_message_text(
        text='正在进行 <b>管理 VM</b>\n\n'
             f'删除实例 <code>{vm_name}</code> 完成',
        chat_id=call.from_user.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )


logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

bot.polling(none_stop=True)
