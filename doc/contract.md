GET /jobs -> {"jobs": [{job1}, {job2}, ...]}

Ahora mismo no espera ningun parametro adicional, al llamarlo
devuelve todos los Jobs almacenados con un 200. Los jobs son devueltos
en una lista, con sus 5 componentes indicamos por data class (y renombrados
para exponerlos al cliente: id, work_type, duration_ms,
result, state) 

Los jobs se encuentran ordenados por sus id (int)

El valor de result se dejara como None -> Null (Json)
hasta que el worker termine.