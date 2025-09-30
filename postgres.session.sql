SELECT 
    id,
    name,
    request,
    description
FROM mon.request;


SELECT 
    id,
    name,
    request,
    description
FROM mon.request;-- 1. Группы
INSERT INTO request_group (id, name, description, handler_type) VALUES
(1, 'system_info', 'Общая информация об устройстве', 'single'),
(2, 'interfaces_summary', 'Сводка по интерфейсам', 'single'),
(3, 'interfaces_details', 'Детальная информация по интерфейсам', 'walk'),
(4, 'mac_table', 'Таблица MAC адресов', 'walk'),
(5, 'arp_table', 'ARP таблица', 'walk'),
(6, 'bridge_info', 'Информация моста', 'single');

-- 2. Привязки
INSERT INTO request_group_ref (group_id, request_id) VALUES
(1,1),(1,2),(1,3),(1,4),(1,5),
(2,6),
(3,44),(3,45),(3,46),(3,47),(3,48),(3,49),(3,50),(3,51),(3,52),(3,53),
(4,7),(4,8),(4,11),
(5,9),(5,12),
(6,10);
