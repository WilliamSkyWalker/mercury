import getpass
import os

import ldap

SERVER = os.environ['LDAP_SERVER']
BASE_DN = os.environ['LDAP_BASE_DN']
EMAIL = os.environ['LDAP_EMAIL']
PASSWORD = os.environ.get('LDAP_PASSWORD') or getpass.getpass('LDAP password: ')

c = ldap.initialize(SERVER)
c.set_option(ldap.OPT_REFERRALS, 0)
c.set_option(ldap.OPT_NETWORK_TIMEOUT, 10)

# Bind with email (UPN) + password directly
c.simple_bind_s(EMAIL, PASSWORD)
print('Bind OK')

r = c.search_s(BASE_DN, ldap.SCOPE_SUBTREE, f'(mail={EMAIL})', ['cn', 'mail', 'displayName', 'sAMAccountName'])
for dn, attrs in r:
    if dn:
        print(f'DN: {dn}')
        print(f'Attrs: {attrs}')

c.unbind_s()
