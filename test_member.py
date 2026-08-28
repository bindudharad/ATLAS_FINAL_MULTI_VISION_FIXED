from atlas.mapping.member_fields import resolve_member_field, section_of, _MEMBER_KEYS_TO_CANONICAL

print('Canonical fields:')
for k, v in _MEMBER_KEYS_TO_CANONICAL.items():
    print(f'  {k} -> {v}')

print()
print('resolve_member_field(App No):', resolve_member_field('App No'))
print('resolve_member_field(MBI Code):', resolve_member_field('MBI Code'))
print('resolve_member_field(Full Name):', resolve_member_field('Full Name'))
print('resolve_member_field(District):', resolve_member_field('District'))
print('resolve_member_field(Member Basic Information):', resolve_member_field('Member Basic Information'))
