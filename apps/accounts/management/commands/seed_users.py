"""
apps/accounts/management/commands/seed_users.py

Usage:
    python manage.py seed_users
    python manage.py seed_users --clear    # deletes ALL seeded users first
    python manage.py seed_users --count 50 # seed only first 50

All passwords: Admin@12345
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.accounts.models import SystemUser


SEED_PASSWORD = 'Admin@12345'

# ─── 200 standalone accounts (no employee link) ───────────────────────────
SEED_USERS = [
    # ── Super Admins (5) ─────────────────────────────────────────────────
    {'username': 'superadmin.reyes',     'role': 'superadmin', 'personal_email': 'reyes.admin@example.com'},
    {'username': 'superadmin.santos',    'role': 'superadmin', 'personal_email': 'santos.admin@example.com'},
    {'username': 'superadmin.garcia',    'role': 'superadmin', 'personal_email': 'garcia.admin@example.com'},
    {'username': 'superadmin.dela_cruz', 'role': 'superadmin', 'personal_email': 'delacruz.admin@example.com'},
    {'username': 'superadmin.mendoza',   'role': 'superadmin', 'personal_email': 'mendoza.admin@example.com'},

    # ── HR Admins (20) ───────────────────────────────────────────────────
    {'username': 'hr.admin.bautista',    'role': 'hr_admin', 'personal_email': 'bautista.hradmin@example.com'},
    {'username': 'hr.admin.castro',      'role': 'hr_admin', 'personal_email': 'castro.hradmin@example.com'},
    {'username': 'hr.admin.villanueva',  'role': 'hr_admin', 'personal_email': 'villanueva.hradmin@example.com'},
    {'username': 'hr.admin.fernandez',   'role': 'hr_admin', 'personal_email': 'fernandez.hradmin@example.com'},
    {'username': 'hr.admin.aquino',      'role': 'hr_admin', 'personal_email': 'aquino.hradmin@example.com'},
    {'username': 'hr.admin.ramos',       'role': 'hr_admin', 'personal_email': 'ramos.hradmin@example.com'},
    {'username': 'hr.admin.torres',      'role': 'hr_admin', 'personal_email': 'torres.hradmin@example.com'},
    {'username': 'hr.admin.pascual',     'role': 'hr_admin', 'personal_email': 'pascual.hradmin@example.com'},
    {'username': 'hr.admin.aguilar',     'role': 'hr_admin', 'personal_email': 'aguilar.hradmin@example.com'},
    {'username': 'hr.admin.robles',      'role': 'hr_admin', 'personal_email': 'robles.hradmin@example.com'},
    {'username': 'hr.admin.evangelista', 'role': 'hr_admin', 'personal_email': 'evangelista.hradmin@example.com'},
    {'username': 'hr.admin.soriano',     'role': 'hr_admin', 'personal_email': 'soriano.hradmin@example.com'},
    {'username': 'hr.admin.navarro',     'role': 'hr_admin', 'personal_email': 'navarro.hradmin@example.com'},
    {'username': 'hr.admin.salazar',     'role': 'hr_admin', 'personal_email': 'salazar.hradmin@example.com'},
    {'username': 'hr.admin.dela_rosa',   'role': 'hr_admin', 'personal_email': 'delarosa.hradmin@example.com'},
    {'username': 'hr.admin.hidalgo',     'role': 'hr_admin', 'personal_email': 'hidalgo.hradmin@example.com'},
    {'username': 'hr.admin.mercado',     'role': 'hr_admin', 'personal_email': 'mercado.hradmin@example.com'},
    {'username': 'hr.admin.cabrera',     'role': 'hr_admin', 'personal_email': 'cabrera.hradmin@example.com'},
    {'username': 'hr.admin.flores',      'role': 'hr_admin', 'personal_email': 'flores.hradmin@example.com'},
    {'username': 'hr.admin.velasco',     'role': 'hr_admin', 'personal_email': 'velasco.hradmin@example.com'},

    # ── HR Staff (50) ────────────────────────────────────────────────────
    {'username': 'hr.staff.abad',        'role': 'hr_staff', 'personal_email': 'abad.hrstaff@example.com'},
    {'username': 'hr.staff.abella',      'role': 'hr_staff', 'personal_email': 'abella.hrstaff@example.com'},
    {'username': 'hr.staff.abesamis',    'role': 'hr_staff', 'personal_email': 'abesamis.hrstaff@example.com'},
    {'username': 'hr.staff.abogado',     'role': 'hr_staff', 'personal_email': 'abogado.hrstaff@example.com'},
    {'username': 'hr.staff.abrea',       'role': 'hr_staff', 'personal_email': 'abrea.hrstaff@example.com'},
    {'username': 'hr.staff.acosta',      'role': 'hr_staff', 'personal_email': 'acosta.hrstaff@example.com'},
    {'username': 'hr.staff.acuña',       'role': 'hr_staff', 'personal_email': 'acuna.hrstaff@example.com'},
    {'username': 'hr.staff.advincula',   'role': 'hr_staff', 'personal_email': 'advincula.hrstaff@example.com'},
    {'username': 'hr.staff.aguila',      'role': 'hr_staff', 'personal_email': 'aguila.hrstaff@example.com'},
    {'username': 'hr.staff.agustin',     'role': 'hr_staff', 'personal_email': 'agustin.hrstaff@example.com'},
    {'username': 'hr.staff.alarcon',     'role': 'hr_staff', 'personal_email': 'aalarcon.hrstaff@example.com'},
    {'username': 'hr.staff.alba',        'role': 'hr_staff', 'personal_email': 'alba.hrstaff@example.com'},
    {'username': 'hr.staff.alcantara',   'role': 'hr_staff', 'personal_email': 'alcantara.hrstaff@example.com'},
    {'username': 'hr.staff.aldana',      'role': 'hr_staff', 'personal_email': 'aldana.hrstaff@example.com'},
    {'username': 'hr.staff.alegre',      'role': 'hr_staff', 'personal_email': 'alegre.hrstaff@example.com'},
    {'username': 'hr.staff.alfaro',      'role': 'hr_staff', 'personal_email': 'alfaro.hrstaff@example.com'},
    {'username': 'hr.staff.almario',     'role': 'hr_staff', 'personal_email': 'almario.hrstaff@example.com'},
    {'username': 'hr.staff.almeda',      'role': 'hr_staff', 'personal_email': 'almeda.hrstaff@example.com'},
    {'username': 'hr.staff.alonte',      'role': 'hr_staff', 'personal_email': 'alonte.hrstaff@example.com'},
    {'username': 'hr.staff.alquiza',     'role': 'hr_staff', 'personal_email': 'alquiza.hrstaff@example.com'},
    {'username': 'hr.staff.altamira',    'role': 'hr_staff', 'personal_email': 'altamira.hrstaff@example.com'},
    {'username': 'hr.staff.alvarado',    'role': 'hr_staff', 'personal_email': 'alvarado.hrstaff@example.com'},
    {'username': 'hr.staff.alvarez',     'role': 'hr_staff', 'personal_email': 'alvarez.hrstaff@example.com'},
    {'username': 'hr.staff.amador',      'role': 'hr_staff', 'personal_email': 'amador.hrstaff@example.com'},
    {'username': 'hr.staff.ambrosio',    'role': 'hr_staff', 'personal_email': 'ambrosio.hrstaff@example.com'},
    {'username': 'hr.staff.amigo',       'role': 'hr_staff', 'personal_email': 'amigo.hrstaff@example.com'},
    {'username': 'hr.staff.amon',        'role': 'hr_staff', 'personal_email': 'amon.hrstaff@example.com'},
    {'username': 'hr.staff.amor',        'role': 'hr_staff', 'personal_email': 'amor.hrstaff@example.com'},
    {'username': 'hr.staff.amparo',      'role': 'hr_staff', 'personal_email': 'amparo.hrstaff@example.com'},
    {'username': 'hr.staff.andal',       'role': 'hr_staff', 'personal_email': 'andal.hrstaff@example.com'},
    {'username': 'hr.staff.andaya',      'role': 'hr_staff', 'personal_email': 'andaya.hrstaff@example.com'},
    {'username': 'hr.staff.angeles',     'role': 'hr_staff', 'personal_email': 'angeles.hrstaff@example.com'},
    {'username': 'hr.staff.anonas',      'role': 'hr_staff', 'personal_email': 'anonas.hrstaff@example.com'},
    {'username': 'hr.staff.antonio',     'role': 'hr_staff', 'personal_email': 'antonio.hrstaff@example.com'},
    {'username': 'hr.staff.anunciacion', 'role': 'hr_staff', 'personal_email': 'anunciacion.hrstaff@example.com'},
    {'username': 'hr.staff.apuya',       'role': 'hr_staff', 'personal_email': 'apuya.hrstaff@example.com'},
    {'username': 'hr.staff.aquino2',     'role': 'hr_staff', 'personal_email': 'aquino2.hrstaff@example.com'},
    {'username': 'hr.staff.araneta',     'role': 'hr_staff', 'personal_email': 'araneta.hrstaff@example.com'},
    {'username': 'hr.staff.arcega',      'role': 'hr_staff', 'personal_email': 'arcega.hrstaff@example.com'},
    {'username': 'hr.staff.arcilla',     'role': 'hr_staff', 'personal_email': 'arcilla.hrstaff@example.com'},
    {'username': 'hr.staff.arcinas',     'role': 'hr_staff', 'personal_email': 'arcinas.hrstaff@example.com'},
    {'username': 'hr.staff.ardiente',    'role': 'hr_staff', 'personal_email': 'ardiente.hrstaff@example.com'},
    {'username': 'hr.staff.arenas',      'role': 'hr_staff', 'personal_email': 'arenas.hrstaff@example.com'},
    {'username': 'hr.staff.arevalo',     'role': 'hr_staff', 'personal_email': 'arevalo.hrstaff@example.com'},
    {'username': 'hr.staff.arguelles',   'role': 'hr_staff', 'personal_email': 'arguelles.hrstaff@example.com'},
    {'username': 'hr.staff.arias',       'role': 'hr_staff', 'personal_email': 'arias.hrstaff@example.com'},
    {'username': 'hr.staff.aricayos',    'role': 'hr_staff', 'personal_email': 'aricayos.hrstaff@example.com'},
    {'username': 'hr.staff.ariniego',    'role': 'hr_staff', 'personal_email': 'ariniego.hrstaff@example.com'},
    {'username': 'hr.staff.arjona',      'role': 'hr_staff', 'personal_email': 'arjona.hrstaff@example.com'},
    {'username': 'hr.staff.arroyo',      'role': 'hr_staff', 'personal_email': 'arroyo.hrstaff@example.com'},

    # ── Viewers (125) ────────────────────────────────────────────────────
    {'username': 'emp.bacalso',       'role': 'viewer', 'personal_email': 'bacalso@example.com'},
    {'username': 'emp.bacani',        'role': 'viewer', 'personal_email': 'bacani@example.com'},
    {'username': 'emp.bacarro',       'role': 'viewer', 'personal_email': 'bacarro@example.com'},
    {'username': 'emp.baclayon',      'role': 'viewer', 'personal_email': 'baclayon@example.com'},
    {'username': 'emp.baclayan',      'role': 'viewer', 'personal_email': 'baclayan@example.com'},
    {'username': 'emp.baclig',        'role': 'viewer', 'personal_email': 'baclig@example.com'},
    {'username': 'emp.bacod',         'role': 'viewer', 'personal_email': 'bacod@example.com'},
    {'username': 'emp.bacolod',       'role': 'viewer', 'personal_email': 'bacolod@example.com'},
    {'username': 'emp.bacolor',       'role': 'viewer', 'personal_email': 'bacolor@example.com'},
    {'username': 'emp.bacosa',        'role': 'viewer', 'personal_email': 'bacosa@example.com'},
    {'username': 'emp.bacoto',        'role': 'viewer', 'personal_email': 'bacoto@example.com'},
    {'username': 'emp.bacquial',      'role': 'viewer', 'personal_email': 'bacquial@example.com'},
    {'username': 'emp.bacsain',       'role': 'viewer', 'personal_email': 'bacsain@example.com'},
    {'username': 'emp.badajos',       'role': 'viewer', 'personal_email': 'badajos@example.com'},
    {'username': 'emp.badal',         'role': 'viewer', 'personal_email': 'badal@example.com'},
    {'username': 'emp.bade',          'role': 'viewer', 'personal_email': 'bade@example.com'},
    {'username': 'emp.badiola',       'role': 'viewer', 'personal_email': 'badiola@example.com'},
    {'username': 'emp.badion',        'role': 'viewer', 'personal_email': 'badion@example.com'},
    {'username': 'emp.baes',          'role': 'viewer', 'personal_email': 'baes@example.com'},
    {'username': 'emp.bagac',         'role': 'viewer', 'personal_email': 'bagac@example.com'},
    {'username': 'emp.bagain',        'role': 'viewer', 'personal_email': 'bagain@example.com'},
    {'username': 'emp.bagalay',       'role': 'viewer', 'personal_email': 'bagalay@example.com'},
    {'username': 'emp.bagalso',       'role': 'viewer', 'personal_email': 'bagalso@example.com'},
    {'username': 'emp.bagaporo',      'role': 'viewer', 'personal_email': 'bagaporo@example.com'},
    {'username': 'emp.bagares',       'role': 'viewer', 'personal_email': 'bagares@example.com'},
    {'username': 'emp.bagasala',      'role': 'viewer', 'personal_email': 'bagasala@example.com'},
    {'username': 'emp.bagasin',       'role': 'viewer', 'personal_email': 'bagasin@example.com'},
    {'username': 'emp.bagasol',       'role': 'viewer', 'personal_email': 'bagasol@example.com'},
    {'username': 'emp.bagayas',       'role': 'viewer', 'personal_email': 'bagayas@example.com'},
    {'username': 'emp.bagaynan',      'role': 'viewer', 'personal_email': 'bagaynan@example.com'},
    {'username': 'emp.bagaipo',       'role': 'viewer', 'personal_email': 'bagaipo@example.com'},
    {'username': 'emp.bagalso2',      'role': 'viewer', 'personal_email': 'bagalso2@example.com'},
    {'username': 'emp.bagatao',       'role': 'viewer', 'personal_email': 'bagatao@example.com'},
    {'username': 'emp.bagon',         'role': 'viewer', 'personal_email': 'bagon@example.com'},
    {'username': 'emp.bagong',        'role': 'viewer', 'personal_email': 'bagong@example.com'},
    {'username': 'emp.bagos',         'role': 'viewer', 'personal_email': 'bagos@example.com'},
    {'username': 'emp.baguio',        'role': 'viewer', 'personal_email': 'baguio@example.com'},
    {'username': 'emp.bagui',         'role': 'viewer', 'personal_email': 'bagui@example.com'},
    {'username': 'emp.bagul',         'role': 'viewer', 'personal_email': 'bagul@example.com'},
    {'username': 'emp.bahala',        'role': 'viewer', 'personal_email': 'bahala@example.com'},
    {'username': 'emp.bajar',         'role': 'viewer', 'personal_email': 'bajar@example.com'},
    {'username': 'emp.bajarin',       'role': 'viewer', 'personal_email': 'bajarin@example.com'},
    {'username': 'emp.bajenting',     'role': 'viewer', 'personal_email': 'bajenting@example.com'},
    {'username': 'emp.bajeta',        'role': 'viewer', 'personal_email': 'bajeta@example.com'},
    {'username': 'emp.bajoc',         'role': 'viewer', 'personal_email': 'bajoc@example.com'},
    {'username': 'emp.bajuyo',        'role': 'viewer', 'personal_email': 'bajuyo@example.com'},
    {'username': 'emp.balagtas',      'role': 'viewer', 'personal_email': 'balagtas@example.com'},
    {'username': 'emp.balais',        'role': 'viewer', 'personal_email': 'balais@example.com'},
    {'username': 'emp.balalio',       'role': 'viewer', 'personal_email': 'balalio@example.com'},
    {'username': 'emp.balan',         'role': 'viewer', 'personal_email': 'balan@example.com'},
    {'username': 'emp.balana',        'role': 'viewer', 'personal_email': 'balana@example.com'},
    {'username': 'emp.balandra',      'role': 'viewer', 'personal_email': 'balandra@example.com'},
    {'username': 'emp.balangatan',    'role': 'viewer', 'personal_email': 'balangatan@example.com'},
    {'username': 'emp.balani',        'role': 'viewer', 'personal_email': 'balani@example.com'},
    {'username': 'emp.balansag',      'role': 'viewer', 'personal_email': 'balansag@example.com'},
    {'username': 'emp.balanza',       'role': 'viewer', 'personal_email': 'balanza@example.com'},
    {'username': 'emp.balaoing',      'role': 'viewer', 'personal_email': 'balaoing@example.com'},
    {'username': 'emp.balaoro',       'role': 'viewer', 'personal_email': 'balaoro@example.com'},
    {'username': 'emp.balaquio',      'role': 'viewer', 'personal_email': 'balaquio@example.com'},
    {'username': 'emp.balarao',       'role': 'viewer', 'personal_email': 'balarao@example.com'},
    {'username': 'emp.balasa',        'role': 'viewer', 'personal_email': 'balasa@example.com'},
    {'username': 'emp.balasabas',     'role': 'viewer', 'personal_email': 'balasabas@example.com'},
    {'username': 'emp.balasico',      'role': 'viewer', 'personal_email': 'balasico@example.com'},
    {'username': 'emp.balasoto',      'role': 'viewer', 'personal_email': 'balasoto@example.com'},
    {'username': 'emp.balatan',       'role': 'viewer', 'personal_email': 'balatan@example.com'},
    {'username': 'emp.balatbat',      'role': 'viewer', 'personal_email': 'balatbat@example.com'},
    {'username': 'emp.balayo',        'role': 'viewer', 'personal_email': 'balayo@example.com'},
    {'username': 'emp.balce',         'role': 'viewer', 'personal_email': 'balce@example.com'},
    {'username': 'emp.balcita',       'role': 'viewer', 'personal_email': 'balcita@example.com'},
    {'username': 'emp.baldago',       'role': 'viewer', 'personal_email': 'baldago@example.com'},
    {'username': 'emp.baldeo',        'role': 'viewer', 'personal_email': 'baldeo@example.com'},
    {'username': 'emp.baldivino',     'role': 'viewer', 'personal_email': 'baldivino@example.com'},
    {'username': 'emp.baldres',       'role': 'viewer', 'personal_email': 'baldres@example.com'},
    {'username': 'emp.balduz',        'role': 'viewer', 'personal_email': 'balduz@example.com'},
    {'username': 'emp.balela',        'role': 'viewer', 'personal_email': 'balela@example.com'},
    {'username': 'emp.balendres',     'role': 'viewer', 'personal_email': 'balendres@example.com'},
    {'username': 'emp.baleria',       'role': 'viewer', 'personal_email': 'baleria@example.com'},
    {'username': 'emp.baleros',       'role': 'viewer', 'personal_email': 'baleros@example.com'},
    {'username': 'emp.bales',         'role': 'viewer', 'personal_email': 'bales@example.com'},
    {'username': 'emp.balestra',      'role': 'viewer', 'personal_email': 'balestra@example.com'},
    {'username': 'emp.baleta',        'role': 'viewer', 'personal_email': 'baleta@example.com'},
    {'username': 'emp.balete',        'role': 'viewer', 'personal_email': 'balete@example.com'},
    {'username': 'emp.baliao',        'role': 'viewer', 'personal_email': 'baliao@example.com'},
    {'username': 'emp.balicao',       'role': 'viewer', 'personal_email': 'balicao@example.com'},
    {'username': 'emp.balicasan',     'role': 'viewer', 'personal_email': 'balicasan@example.com'},
    {'username': 'emp.balido',        'role': 'viewer', 'personal_email': 'balido@example.com'},
    {'username': 'emp.balidoy',       'role': 'viewer', 'personal_email': 'balidoy@example.com'},
    {'username': 'emp.baligad',       'role': 'viewer', 'personal_email': 'baligad@example.com'},
    {'username': 'emp.baligasa',      'role': 'viewer', 'personal_email': 'baligasa@example.com'},
    {'username': 'emp.baligod',       'role': 'viewer', 'personal_email': 'baligod@example.com'},
    {'username': 'emp.balijon',       'role': 'viewer', 'personal_email': 'balijon@example.com'},
    {'username': 'emp.balili',        'role': 'viewer', 'personal_email': 'balili@example.com'},
    {'username': 'emp.balilo',        'role': 'viewer', 'personal_email': 'balilo@example.com'},
    {'username': 'emp.balimbing',     'role': 'viewer', 'personal_email': 'balimbing@example.com'},
    {'username': 'emp.balinado',      'role': 'viewer', 'personal_email': 'balinado@example.com'},
    {'username': 'emp.balinag',       'role': 'viewer', 'personal_email': 'balinag@example.com'},
    {'username': 'emp.balingasa',     'role': 'viewer', 'personal_email': 'balingasa@example.com'},
    {'username': 'emp.balinggit',     'role': 'viewer', 'personal_email': 'balinggit@example.com'},
    {'username': 'emp.balino',        'role': 'viewer', 'personal_email': 'balino@example.com'},
    {'username': 'emp.balio',         'role': 'viewer', 'personal_email': 'balio@example.com'},
    {'username': 'emp.baliobal',      'role': 'viewer', 'personal_email': 'baliobal@example.com'},
    {'username': 'emp.baliog',        'role': 'viewer', 'personal_email': 'baliog@example.com'},
    {'username': 'emp.baliola',       'role': 'viewer', 'personal_email': 'baliola@example.com'},
    {'username': 'emp.baliong',       'role': 'viewer', 'personal_email': 'baliong@example.com'},
    {'username': 'emp.balios',        'role': 'viewer', 'personal_email': 'balios@example.com'},
    {'username': 'emp.balirang',      'role': 'viewer', 'personal_email': 'balirang@example.com'},
    {'username': 'emp.balisado',      'role': 'viewer', 'personal_email': 'balisado@example.com'},
    {'username': 'emp.balisacan',     'role': 'viewer', 'personal_email': 'balisacan@example.com'},
    {'username': 'emp.balisado2',     'role': 'viewer', 'personal_email': 'balisado2@example.com'},
    {'username': 'emp.balisong',      'role': 'viewer', 'personal_email': 'balisong@example.com'},
    {'username': 'emp.balistoy',      'role': 'viewer', 'personal_email': 'balistoy@example.com'},
    {'username': 'emp.balita',        'role': 'viewer', 'personal_email': 'balita@example.com'},
    {'username': 'emp.balite',        'role': 'viewer', 'personal_email': 'balite@example.com'},
    {'username': 'emp.balitog',       'role': 'viewer', 'personal_email': 'balitog@example.com'},
    {'username': 'emp.balitong',      'role': 'viewer', 'personal_email': 'balitong@example.com'},
    {'username': 'emp.baliuag',       'role': 'viewer', 'personal_email': 'baliuag@example.com'},
    {'username': 'emp.baliyos',       'role': 'viewer', 'personal_email': 'baliyos@example.com'},
    {'username': 'emp.balla',         'role': 'viewer', 'personal_email': 'balla@example.com'},
    {'username': 'emp.ballad',        'role': 'viewer', 'personal_email': 'ballad@example.com'},
    {'username': 'emp.ballaran',      'role': 'viewer', 'personal_email': 'ballaran@example.com'},
    {'username': 'emp.ballenas',      'role': 'viewer', 'personal_email': 'ballenas@example.com'},
    {'username': 'emp.ballesteros',   'role': 'viewer', 'personal_email': 'ballesteros@example.com'},
    {'username': 'emp.balleza',       'role': 'viewer', 'personal_email': 'balleza@example.com'},
    {'username': 'emp.balmaceda',     'role': 'viewer', 'personal_email': 'balmaceda@example.com'},
    {'username': 'emp.balmeo',        'role': 'viewer', 'personal_email': 'balmeo@example.com'},
    {'username': 'emp.balmores',      'role': 'viewer', 'personal_email': 'balmores@example.com'},
    {'username': 'emp.balmoris',      'role': 'viewer', 'personal_email': 'balmoris@example.com'},
    {'username': 'emp.balmun',        'role': 'viewer', 'personal_email': 'balmun@example.com'},
    {'username': 'emp.balobalo',      'role': 'viewer', 'personal_email': 'balobalo@example.com'},
    {'username': 'emp.balocawit',     'role': 'viewer', 'personal_email': 'balocawit@example.com'},
    {'username': 'emp.balogo',        'role': 'viewer', 'personal_email': 'balogo@example.com'},
    {'username': 'emp.balois',        'role': 'viewer', 'personal_email': 'balois@example.com'},
    {'username': 'emp.baloloy',       'role': 'viewer', 'personal_email': 'baloloy@example.com'},
    {'username': 'emp.balona',        'role': 'viewer', 'personal_email': 'balona@example.com'},
    {'username': 'emp.balonzo',       'role': 'viewer', 'personal_email': 'balonzo@example.com'},
    {'username': 'emp.baloran',       'role': 'viewer', 'personal_email': 'baloran@example.com'},
    {'username': 'emp.balorin',       'role': 'viewer', 'personal_email': 'balorin@example.com'},
    {'username': 'emp.balos',         'role': 'viewer', 'personal_email': 'balos@example.com'},
    {'username': 'emp.balot',         'role': 'viewer', 'personal_email': 'balot@example.com'},
    {'username': 'emp.balote',        'role': 'viewer', 'personal_email': 'balote@example.com'},
    {'username': 'emp.baloyo',        'role': 'viewer', 'personal_email': 'baloyo@example.com'},
    {'username': 'emp.balsa',         'role': 'viewer', 'personal_email': 'balsa@example.com'},
    {'username': 'emp.balsaga',       'role': 'viewer', 'personal_email': 'balsaga@example.com'},
    {'username': 'emp.balsalobre',    'role': 'viewer', 'personal_email': 'balsalobre@example.com'},
    {'username': 'emp.balsamo',       'role': 'viewer', 'personal_email': 'balsamo@example.com'},
    {'username': 'emp.balsiña',       'role': 'viewer', 'personal_email': 'balsina@example.com'},
    {'username': 'emp.baltazar',      'role': 'viewer', 'personal_email': 'baltazar@example.com'},
    {'username': 'emp.baltero',       'role': 'viewer', 'personal_email': 'baltero@example.com'},
    {'username': 'emp.baltezar',      'role': 'viewer', 'personal_email': 'baltezar@example.com'},
    {'username': 'emp.baluca',        'role': 'viewer', 'personal_email': 'baluca@example.com'},
    {'username': 'emp.balucas',       'role': 'viewer', 'personal_email': 'balucas@example.com'},
    {'username': 'emp.balucos',       'role': 'viewer', 'personal_email': 'balucos@example.com'},
    {'username': 'emp.balug',         'role': 'viewer', 'personal_email': 'balug@example.com'},
    {'username': 'emp.balugo',        'role': 'viewer', 'personal_email': 'balugo@example.com'},
    {'username': 'emp.balugon',       'role': 'viewer', 'personal_email': 'balugon@example.com'},
    {'username': 'emp.balunan',       'role': 'viewer', 'personal_email': 'balunan@example.com'},
    {'username': 'emp.balunda',       'role': 'viewer', 'personal_email': 'balunda@example.com'},
    {'username': 'emp.balungay',      'role': 'viewer', 'personal_email': 'balungay@example.com'},
    {'username': 'emp.balutan',       'role': 'viewer', 'personal_email': 'balutan@example.com'},
    {'username': 'emp.baluyos',       'role': 'viewer', 'personal_email': 'baluyos@example.com'},
    {'username': 'emp.balverde',      'role': 'viewer', 'personal_email': 'balverde@example.com'},
    {'username': 'emp.balyan',        'role': 'viewer', 'personal_email': 'balyan@example.com'},
    {'username': 'emp.balyao',        'role': 'viewer', 'personal_email': 'balyao@example.com'},
]


class Command(BaseCommand):
    help = 'Seed 200 standalone development system user accounts (no employee link)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete existing seeded users before creating',
        )
        parser.add_argument(
            '--count',
            type=int,
            default=None,
            help='Only seed the first N users from the list',
        )

    def handle(self, *args, **options):
        users_to_seed = SEED_USERS
        if options['count']:
            users_to_seed = SEED_USERS[:options['count']]

        if options['clear']:
            usernames = [u['username'] for u in users_to_seed]
            deleted, _ = SystemUser.objects.filter(username__in=usernames).delete()
            self.stdout.write(self.style.WARNING(f'Cleared {deleted} existing seeded user(s).'))

        created = 0
        skipped = 0
        errors  = 0

        with transaction.atomic():
            for seed in users_to_seed:
                username = seed['username']
                email    = seed['personal_email']

                # Skip if username already exists
                if SystemUser.objects.filter(username=username).exists():
                    self.stdout.write(f'  SKIP  {username:35} — username exists')
                    skipped += 1
                    continue

                # Skip if email already exists
                if SystemUser.objects.filter(personal_email__iexact=email).exists():
                    self.stdout.write(f'  SKIP  {username:35} — email exists')
                    skipped += 1
                    continue

                try:
                    user = SystemUser(
                        username       = username,
                        role           = seed['role'],
                        personal_email = email,
                        employee       = None,   # no employee link
                        is_active      = True,
                        is_deleted     = False,
                    )
                    user.set_password(SEED_PASSWORD)
                    user.save()

                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  CREATE {username:35} [{seed["role"]:12}]  {email}'
                        )
                    )
                    created += 1

                except Exception as exc:
                    self.stdout.write(
                        self.style.ERROR(f'  ERROR  {username} — {exc}')
                    )
                    errors += 1

        self.stdout.write('')
        self.stdout.write('─' * 60)
        self.stdout.write(self.style.SUCCESS(f'  Created : {created}'))
        if skipped:
            self.stdout.write(self.style.WARNING(f'  Skipped : {skipped}'))
        if errors:
            self.stdout.write(self.style.ERROR(f'  Errors  : {errors}'))
        self.stdout.write(f'  Total   : {len(users_to_seed)}')
        self.stdout.write('─' * 60)
        self.stdout.write(self.style.WARNING(f'  Default password: {SEED_PASSWORD}'))
        self.stdout.write(self.style.WARNING('  Change all passwords before production!'))