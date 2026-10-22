# Ism nusxalarini bir martada tuzatish: Instructor.instructor_name
# Employee.employee_name'dan, undan pastdagi barcha nusxalar (Jadval Yozuvi,
# Dars Natijasi, Kassa.party_name, ...) zanjir bo'yicha yangilanadi.
# O'qituvchi ismlari hamma joyda Employee'dagi TO'LIQ ism bo'ladi.
import frappe


def execute():
    from target_zenit.ism_sync import backfill

    backfill()
