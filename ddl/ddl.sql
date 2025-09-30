-- mon.element_type definition

-- Drop table

-- DROP TABLE mon.element_type;

CREATE TABLE mon.element_type (
	id int4 DEFAULT nextval('mon.seq_element_type_id'::regclass) NOT NULL,
	"name" varchar(100) NULL,
	description varchar(200) NULL,
	CONSTRAINT element_type_pkey PRIMARY KEY (id)
);
COMMENT ON TABLE mon.element_type IS 'Types of monitored elements';



-- Drop table

-- DROP TABLE mon."handler";

CREATE TABLE mon."handler" (
	id int4 DEFAULT nextval('mon.seq_handler_id'::regclass) NOT NULL,
	"name" varchar(100) NULL,
	proc varchar(128) NULL,
	CONSTRAINT handler_pkey PRIMARY KEY (id)
);
COMMENT ON TABLE mon."handler" IS 'Request handlers/processors';


-- mon.node definition

-- Drop table

-- DROP TABLE mon.node;

CREATE TABLE mon.node (
	id int4 DEFAULT nextval('mon.seq_node_id'::regclass) NOT NULL,
	"name" varchar(30) NOT NULL,
	community varchar(100) DEFAULT 'public_cisco'::character varying NULL,
	rwcommunity varchar(100) NULL,
	manage bool DEFAULT true NOT NULL,
	sdi_id int8 NULL,
	vendor varchar(250) NULL,
	"owner" varchar(250) DEFAULT '3'::character varying NOT NULL,
	snmp_last_dt timestamp NULL,
	icmp_last_dt timestamp NULL,
	ssh_last_dt timestamp NULL,
	first_dt timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	iperf int4 NULL,
	username varchar(24) DEFAULT NULL::character varying NULL,
	passwd varchar(24) NULL,
	sysname varchar(255) NULL,
	nf_ident varchar(20) NULL,
	sysobjectid varchar(255) NULL,
	sysuptime timestamp NULL,
	syscontact varchar(255) NULL,
	syslocation varchar(255) NULL,
	sysconfigname varchar(1024) NULL,
	chassisserialnumberstring varchar(200) NULL,
	mac_ssh_last_dt timestamp NULL,
	arp_ssh_last_dt timestamp NULL,
	ssh_v mon."ssh_version" DEFAULT 2 NOT NULL,
	ipforwarding int4 NULL,
	expect varchar(20) NULL,
	timeout int4 DEFAULT 500 NULL,
	dt timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	sn varchar(1024) NULL,
	expect_in varchar(255) NULL,
	expect_out varchar(255) NULL,
	unmanage_to_dt timestamp NULL,
	name_pref varchar(1024) NULL,
	eosl date NULL,
	product_dt date NULL,
	sysname_post varchar(20) NULL,
	cfg_ssh_last_dt timestamp NULL,
	CONSTRAINT node_ipaddress_unique UNIQUE (ipaddress),
	CONSTRAINT node_pkey PRIMARY KEY (id)
);
CREATE INDEX idx_node_manage ON mon.node USING btree (manage) WHERE (manage = true);
CREATE INDEX idx_node_name ON mon.node USING btree (name);
CREATE INDEX idx_node_sdi_id ON mon.node USING btree (sdi_id);
CREATE INDEX idx_node_snmp_last_dt ON mon.node USING btree (snmp_last_dt);
CREATE INDEX idx_node_sysname ON mon.node USING btree (sysname);
CREATE INDEX idx_node_sysobjectid ON mon.node USING btree (sysobjectid);
COMMENT ON TABLE mon.node IS 'Network devices/nodes being monitored';

-- Table Triggers

create trigger node_set_created_dt_trg before
insert
    on
    mon.node for each row execute function mon.trg_set_created_dt();
create trigger node_set_updated_dt_trg before
update
    on
    mon.node for each row execute function mon.trg_set_updated_dt();


-- mon.node_group definition

-- Drop table

-- DROP TABLE mon.node_group;

CREATE TABLE mon.node_group (
	id int4 DEFAULT nextval('mon.seq_node_group_id'::regclass) NOT NULL,
	"name" varchar(100) NULL,
	"type" varchar(200) NULL,
	site int4 NULL,
	description varchar(200) NULL,
	net int4 NULL,
	id_ok int4 NULL,
	CONSTRAINT node_group_pkey PRIMARY KEY (id)
);
COMMENT ON TABLE mon.node_group IS 'Groups of network nodes';


-- mon.request_type definition

-- Drop table

-- DROP TABLE mon.request_type;

CREATE TABLE mon.request_type (
	id int4 DEFAULT nextval('mon.seq_request_type_id'::regclass) NOT NULL,
	"name" varchar(200) NULL,
	descr varchar(500) NULL,
	CONSTRAINT request_type_pkey PRIMARY KEY (id)
);
COMMENT ON TABLE mon.request_type IS 'Types of monitoring requests';


-- mon."element" definition

-- Drop table

-- DROP TABLE mon."element";

CREATE TABLE mon."element" (
	id int4 DEFAULT nextval('mon.seq_element_id'::regclass) NOT NULL,
	"name" varchar(100) NULL,
	snmp_id int4 NULL,
	manage bool DEFAULT true NULL,
	deleted bool DEFAULT false NULL,
	node_id int4 NOT NULL,
	element_type_id int4 DEFAULT 1 NOT NULL,
	description varchar(200) NULL,
	first_dt timestamp NULL,
	dt timestamp NULL,
	CONSTRAINT element_node_snmp_unique UNIQUE (node_id, snmp_id),
	CONSTRAINT element_pkey PRIMARY KEY (id),
	CONSTRAINT element_element_type_id_fkey FOREIGN KEY (element_type_id) REFERENCES mon.element_type(id),
	CONSTRAINT element_node_id_fkey FOREIGN KEY (node_id) REFERENCES mon.node(id) ON DELETE CASCADE
);
CREATE INDEX idx_element_deleted ON mon.element USING btree (deleted) WHERE (deleted = false);
CREATE INDEX idx_element_node_id ON mon.element USING btree (node_id);
COMMENT ON TABLE mon."element" IS 'Monitored elements on nodes';

-- Table Triggers

create trigger element_set_created_dt_trg before
insert
    on
    mon.element for each row execute function mon.trg_set_created_dt();
create trigger element_set_updated_dt_trg before
update
    on
    mon.element for each row execute function mon.trg_set_updated_dt();


-- mon.mac_addresses definition

-- Drop table

-- DROP TABLE mon.mac_addresses;

CREATE TABLE mon.mac_addresses (
	id serial4 NOT NULL,
	node_id int4 NOT NULL,
	interface_id int4 NULL,
	mac_address macaddr NOT NULL, -- MAC-адрес устройства
	ip_address inet NULL, -- IP-адрес устройства (если известен)
	vlan_id int4 NULL, -- VLAN ID
	first_seen timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	last_seen timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	status varchar(20) DEFAULT 'ACTIVE'::character varying NULL, -- Статус: ACTIVE, INACTIVE
	CONSTRAINT mac_addresses_pkey PRIMARY KEY (id),
	CONSTRAINT mac_addresses_interface_fk FOREIGN KEY (interface_id) REFERENCES mon."element"(id) ON DELETE SET NULL,
	CONSTRAINT mac_addresses_node_fk FOREIGN KEY (node_id) REFERENCES mon.node(id) ON DELETE CASCADE
);
CREATE INDEX idx_mac_addresses_interface ON mon.mac_addresses USING btree (interface_id);
CREATE INDEX idx_mac_addresses_last_seen ON mon.mac_addresses USING btree (last_seen);
CREATE INDEX idx_mac_addresses_mac ON mon.mac_addresses USING btree (mac_address);
CREATE INDEX idx_mac_addresses_node ON mon.mac_addresses USING btree (node_id);
CREATE INDEX idx_mac_addresses_status ON mon.mac_addresses USING btree (status) WHERE ((status)::text = 'ACTIVE'::text);
CREATE UNIQUE INDEX idx_mac_addresses_unique ON mon.mac_addresses USING btree (node_id, mac_address) WHERE ((status)::text = 'ACTIVE'::text);
COMMENT ON TABLE mon.mac_addresses IS 'Таблица MAC-адресов с коммутаторов';

-- Column comments

COMMENT ON COLUMN mon.mac_addresses.mac_address IS 'MAC-адрес устройства';
COMMENT ON COLUMN mon.mac_addresses.ip_address IS 'IP-адрес устройства (если известен)';
COMMENT ON COLUMN mon.mac_addresses.vlan_id IS 'VLAN ID';
COMMENT ON COLUMN mon.mac_addresses.status IS 'Статус: ACTIVE, INACTIVE';


-- mon.node_group_ref definition

-- Drop table

-- DROP TABLE mon.node_group_ref;

CREATE TABLE mon.node_group_ref (
	id int4 DEFAULT nextval('mon.seq_node_group_ref_id'::regclass) NOT NULL,
	group_id int4 NOT NULL,
	node_id int4 NOT NULL,
	dt timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	CONSTRAINT node_group_ref_pkey PRIMARY KEY (id),
	CONSTRAINT node_group_ref_unique UNIQUE (group_id, node_id),
	CONSTRAINT node_group_ref_group_id_fkey FOREIGN KEY (group_id) REFERENCES mon.node_group(id),
	CONSTRAINT node_group_ref_node_id_fkey FOREIGN KEY (node_id) REFERENCES mon.node(id) ON DELETE CASCADE
);
CREATE INDEX idx_node_group_ref_composite ON mon.node_group_ref USING btree (group_id, node_id);
CREATE INDEX idx_node_group_ref_group_id ON mon.node_group_ref USING btree (group_id);
CREATE INDEX idx_node_group_ref_node_id ON mon.node_group_ref USING btree (node_id);
COMMENT ON TABLE mon.node_group_ref IS 'References between node groups and nodes';


-- mon.request definition

-- Drop table

-- DROP TABLE mon.request;

CREATE TABLE mon.request (
	id int4 DEFAULT nextval('mon.seq_request_id'::regclass) NOT NULL,
	"name" varchar(100) NULL,
	request text NULL,
	description varchar(1024) NULL,
	prefix varchar(120) NULL,
	postfix varchar(120) NULL,
	manage bool NOT NULL,
	request_type_id int4 NULL,
	"template" varchar(100) NULL,
	comment_ text NULL,
	CONSTRAINT request_name_description_unique UNIQUE (name, description),
	CONSTRAINT request_pkey PRIMARY KEY (id),
	CONSTRAINT request_request_type_id_fkey FOREIGN KEY (request_type_id) REFERENCES mon.request_type(id)
);
COMMENT ON TABLE mon.request IS 'Monitoring requests definitions';


-- mon.request_group definition

-- Drop table

-- DROP TABLE mon.request_group;

CREATE TABLE mon.request_group (
	id int4 DEFAULT nextval('mon.seq_request_group_id'::regclass) NOT NULL,
	"name" varchar(100) NULL,
	type_id int4 NOT NULL,
	handler_id int4 NOT NULL,
	description varchar(200) NULL,
	tag varchar(20) NULL,
	sort int4 NULL,
	manage bool DEFAULT true NULL,
	CONSTRAINT request_group_name_key UNIQUE (name),
	CONSTRAINT request_group_pkey PRIMARY KEY (id),
	CONSTRAINT request_group_handler_id_fkey FOREIGN KEY (handler_id) REFERENCES mon."handler"(id),
	CONSTRAINT request_group_type_id_fkey FOREIGN KEY (type_id) REFERENCES mon.element_type(id)
);
COMMENT ON TABLE mon.request_group IS 'Groups of monitoring requests';


-- mon.request_group_ref definition

-- Drop table

-- DROP TABLE mon.request_group_ref;

CREATE TABLE mon.request_group_ref (
	id int4 DEFAULT nextval('mon.seq_request_group_ref_id'::regclass) NOT NULL,
	group_id int4 NOT NULL,
	request_id int4 NOT NULL,
	timeout int4 NULL,
	CONSTRAINT request_group_ref_pkey PRIMARY KEY (id),
	CONSTRAINT request_group_ref_unique UNIQUE (group_id, request_id),
	CONSTRAINT request_group_ref_group_id_fkey FOREIGN KEY (group_id) REFERENCES mon.request_group(id) ON DELETE CASCADE,
	CONSTRAINT request_group_ref_request_id_fkey FOREIGN KEY (request_id) REFERENCES mon.request(id) ON DELETE CASCADE
);
CREATE INDEX idx_request_group_ref_group_id ON mon.request_group_ref USING btree (group_id);
CREATE INDEX idx_request_group_ref_request_id ON mon.request_group_ref USING btree (request_id);
COMMENT ON TABLE mon.request_group_ref IS 'References between request groups and requests';


-- mon.task definition

-- Drop table

-- DROP TABLE mon.task;

CREATE TABLE mon.task (
	id int4 DEFAULT nextval('mon.seq_task_id'::regclass) NOT NULL,
	node_group_id int4 NOT NULL,
	request_group_id int4 NOT NULL,
	"name" varchar(100) NOT NULL,
	description varchar(200) NULL,
	CONSTRAINT task_pkey PRIMARY KEY (id),
	CONSTRAINT task_node_group_id_fkey FOREIGN KEY (node_group_id) REFERENCES mon.node_group(id),
	CONSTRAINT task_request_group_id_fkey FOREIGN KEY (request_group_id) REFERENCES mon.request_group(id)
);
COMMENT ON TABLE mon.task IS 'Scheduled monitoring tasks';


-- mon.crontab definition

-- Drop table

-- DROP TABLE mon.crontab;

CREATE TABLE mon.crontab (
	id serial4 NOT NULL,
	minutes int4 NULL,
	hours int4 NULL,
	days int4 NULL,
	startdt timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	lastdt timestamp NULL,
	status varchar(30) DEFAULT 'ACTIVE'::character varying NULL,
	task_id int4 NOT NULL,
	agent varchar(30) DEFAULT 'ANY'::character varying NULL,
	j_id int4 NULL,
	CONSTRAINT crontab_pkey PRIMARY KEY (id),
	CONSTRAINT crontab_task_fk FOREIGN KEY (task_id) REFERENCES mon.task(id) ON DELETE CASCADE
);
CREATE INDEX idx_crontab_agent ON mon.crontab USING btree (agent);
CREATE INDEX idx_crontab_lastdt ON mon.crontab USING btree (lastdt);
CREATE INDEX idx_crontab_schedule ON mon.crontab USING btree (minutes, hours, days);
CREATE INDEX idx_crontab_status ON mon.crontab USING btree (status) WHERE ((status)::text = 'ACTIVE'::text);
CREATE INDEX idx_crontab_task ON mon.crontab USING btree (task_id);
COMMENT ON TABLE mon.crontab IS 'Расписание выполнения задач мониторинга';


-- mon.journal definition

-- Drop table

-- DROP TABLE mon.journal;

CREATE TABLE mon.journal (
	id int4 DEFAULT nextval('mon.seq_journal_id'::regclass) NOT NULL,
	startdt timestamp NULL,
	enddt timestamp NULL,
	task_id int4 NULL,
	CONSTRAINT journal_pkey PRIMARY KEY (id),
	CONSTRAINT journal_task_id_fkey FOREIGN KEY (task_id) REFERENCES mon.task(id) ON DELETE CASCADE
);
CREATE INDEX idx_journal_startdt ON mon.journal USING brin (startdt);
CREATE INDEX idx_journal_task_id ON mon.journal USING btree (task_id);
COMMENT ON TABLE mon.journal IS 'Execution journal for monitoring tasks';


-- mon."result" definition

-- Drop table

-- DROP TABLE mon."result";

CREATE TABLE mon."result" (
	id int4 DEFAULT nextval('mon.seq_result_id'::regclass) NOT NULL,
	node_id int4 NOT NULL,
	request_id int4 NOT NULL,
	index_id int4 NULL,
	journal_id int4 NOT NULL,
	val text NULL,
	dt timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	"key" varchar(500) NULL,
	cval text NULL,
	duration int4 NULL,
	err text NULL,
	CONSTRAINT result_pkey PRIMARY KEY (id),
	CONSTRAINT result_index_id_fkey FOREIGN KEY (index_id) REFERENCES mon."element"(id) ON DELETE SET NULL,
	CONSTRAINT result_journal_id_fkey FOREIGN KEY (journal_id) REFERENCES mon.journal(id) ON DELETE CASCADE,
	CONSTRAINT result_node_id_fkey FOREIGN KEY (node_id) REFERENCES mon.node(id) ON DELETE CASCADE,
	CONSTRAINT result_request_id_fkey FOREIGN KEY (request_id) REFERENCES mon.request(id) ON DELETE CASCADE
);
CREATE INDEX idx_result_dt ON mon.result USING brin (dt);
CREATE INDEX idx_result_index_id ON mon.result USING btree (index_id);
CREATE INDEX idx_result_journal_id ON mon.result USING btree (journal_id);
CREATE INDEX idx_result_key ON mon.result USING btree (key);
CREATE INDEX idx_result_node_id ON mon.result USING btree (node_id);
CREATE INDEX idx_result_request_id ON mon.result USING btree (request_id);
COMMENT ON TABLE mon."result" IS 'Results of monitoring requests execution';

-- Table Triggers

create trigger result_set_dt_trg before
insert
    on
    mon.result for each row execute function mon.trg_result_set_dt();


-- mon.node_status_detailed source

CREATE OR REPLACE VIEW mon.node_status_detailed
AS SELECT n.id,
    n.name,
    n.ipaddress,
    n.manage,
        CASE
            WHEN n.snmp_last_dt > (CURRENT_TIMESTAMP - '00:15:00'::interval) THEN 'online'::text
            ELSE 'offline'::text
        END AS status,
    n.snmp_last_dt,
    count(r.id) AS result_count,
    max(r.dt) AS last_result_dt
   FROM mon.node n
     LEFT JOIN mon.result r ON n.id = r.node_id
  WHERE n.manage = true
  GROUP BY n.id, n.name, n.ipaddress, n.manage, n.snmp_last_dt;

COMMENT ON VIEW mon.node_status_detailed IS 'Detailed node status with result statistics';




-- Проверка структуры таблицы
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'mac_addresses' AND table_schema = 'mon';




-- Таблица для хранения интерфейсов устройств
CREATE TABLE mon.interfaces (
    id SERIAL PRIMARY KEY,
    node_id INTEGER NOT NULL REFERENCES mon.node(id) ON DELETE CASCADE,
    if_index INTEGER NOT NULL,
    if_name VARCHAR(255),
    if_descr TEXT,
    if_type INTEGER,
    if_mtu INTEGER,
    if_speed BIGINT,
    if_phys_address MACADDR,
    if_admin_status INTEGER,
    if_oper_status INTEGER,
    if_last_change BIGINT,
    if_alias TEXT,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    UNIQUE(node_id, if_index)
);

-- Индексы для оптимизации
CREATE INDEX idx_interfaces_node_id ON mon.interfaces(node_id);
CREATE INDEX idx_interfaces_status ON mon.interfaces(status);
CREATE INDEX idx_interfaces_last_seen ON mon.interfaces(last_seen);

-- Таблица для хранения статистики интерфейсов
CREATE TABLE mon.interface_stats (
    id SERIAL PRIMARY KEY,
    interface_id INTEGER NOT NULL REFERENCES mon.interfaces(id) ON DELETE CASCADE,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    if_in_octets BIGINT,
    if_in_ucast_pkts BIGINT,
    if_in_errors BIGINT,
    if_out_octets BIGINT,
    if_out_ucast_pkts BIGINT,
    if_out_errors BIGINT
);

-- Индексы для статистики
CREATE INDEX idx_interface_stats_interface_id ON mon.interface_stats(interface_id);
CREATE INDEX idx_interface_stats_collected_at ON mon.interface_stats(collected_at);

-- Группа запросов для инвентаризации интерфейсов
INSERT INTO mon.request_group (name, description, handler_id, type_id, manage) 
VALUES ('Interface Discovery', 'Обнаружение и инвентаризация интерфейсов', 1, 1, true)
ON CONFLICT (name) DO NOTHING;

-- Запросы для сбора информации об интерфейсах
INSERT INTO mon.request (name, request, description, request_type_id, manage) VALUES
('ifIndex'      , '1.3.6.1.2.1.2.2.1.1', 'Индекс интерфейса', 1, true),
('ifDescr'      , '1.3.6.1.2.1.2.2.1.2', 'Описание интерфейса', 1, true),
('ifType'       , '1.3.6.1.2.1.2.2.1.3', 'Тип интерфейса', 1, true),
('ifMtu'        , '1.3.6.1.2.1.2.2.1.4', 'MTU интерфейса', 1, true),
('ifSpeed'      , '1.3.6.1.2.1.2.2.1.5', 'Скорость интерфейса', 1, true),
('ifPhysAddress', '1.3.6.1.2.1.2.2.1.6', 'Физический адрес', 1, true),
('ifAdminStatus', '1.3.6.1.2.1.2.2.1.7', 'Административный статус', 1, true),
('ifOperStatus' , '1.3.6.1.2.1.2.2.1.8', 'Операционный статус', 1, true),
('ifLastChange' , '1.3.6.1.2.1.2.2.1.9', 'Время последнего изменения', 1, true),
('ifAlias'      , '1.3.6.1.2.1.31.1.1.1.18', 'Алиас интерфейса', 1, true)
ON CONFLICT (name) DO NOTHING;

-- Привязка запросов к группе
INSERT INTO mon.request_group_ref (group_id, request_id, timeout)
SELECT 
    rg.id, r.id, 5000
FROM mon.request_group rg, mon.request r 
WHERE rg.name = 'Interface Discovery' 
AND r.name IN ('ifIndex', 'ifDescr', 'ifType', 'ifMtu', 'ifSpeed', 'ifPhysAddress', 
               'ifAdminStatus', 'ifOperStatus', 'ifLastChange', 'ifAlias')
ON CONFLICT DO NOTHING;
commit;
-- Задача для инвентаризации интерфейсов
INSERT INTO mon.task (name, description, node_group_id, request_group_id, manage)
SELECT 
    'Interface Inventory', 
    'Инвентаризация интерфейсов устройств',
    ng.id, 
    rg.id,
    true
FROM mon.node_group ng, mon.request_group rg
WHERE ng.name = 'Default' AND rg.name = 'Interface Discovery'
--ON CONFLICT (name) DO nothing
;

-- Расписание для инвентаризации (раз в сутки)
INSERT INTO mon.crontab (minutes, hours, days, task_id, agent, status)
SELECT 
    1, 0, 0,  -- Каждый день в 2:00
    t.id,
    'ANY',
    'ACTIVE'
FROM mon.task t
WHERE t.name = 'Interface Inventory'
--ON CONFLICT (task_id, agent) DO UPDATE SET status = 'ACTIVE';


-- Проверка конфигурации
SELECT 
    t.name as task_name,
    rg.name as request_group_name,
    rg.handler_id,
    r.name as request_name,
    r.request as oid
FROM mon.task t
JOIN mon.request_group rg ON t.request_group_id = rg.id
JOIN mon.request_group_ref rgr ON rg.id = rgr.group_id
JOIN mon.request r ON rgr.request_id = r.id
WHERE t.name = 'Interface Inventory';


-- ======================================================================
-- Additional DDL extracted from live database: interface inventory, IPs, ARP
-- These objects are created with IF NOT EXISTS to make the DDL idempotent
-- ======================================================================

-- Table for interface inventory (per-node, per-ifIndex)
CREATE TABLE IF NOT EXISTS mon.interface_inventory (
	id SERIAL PRIMARY KEY,
	node_id INTEGER NOT NULL REFERENCES mon.node(id) ON DELETE CASCADE,
	if_index INTEGER NOT NULL,
	if_name VARCHAR(255),
	if_descr TEXT,
	if_type INTEGER,
	if_mtu INTEGER,
	if_speed BIGINT,
	if_phys_address MACADDR,
	if_admin_status INTEGER,
	if_oper_status INTEGER,
	if_last_change BIGINT,
	if_alias TEXT,
	discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	status VARCHAR(20) DEFAULT 'ACTIVE',
	UNIQUE(node_id, if_index)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_interface_inventory_node_ifindex ON mon.interface_inventory(node_id, if_index);


-- Table for mapping IP addresses to interfaces on a node
CREATE TABLE IF NOT EXISTS mon.interface_ip (
	id SERIAL PRIMARY KEY,
	node_id INTEGER NOT NULL REFERENCES mon.node(id) ON DELETE CASCADE,
	if_index INTEGER NOT NULL,
	ip_address INET NOT NULL,
	first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	source VARCHAR(50)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_interface_ip_node_ifindex_ip ON mon.interface_ip(node_id, if_index, ip_address);


-- ARP table (IP -> MAC learned from IPNetToMedia/arp)
CREATE TABLE IF NOT EXISTS mon.arp_table (
	id SERIAL PRIMARY KEY,
	node_id INTEGER NOT NULL REFERENCES mon.node(id) ON DELETE CASCADE,
	ip_address INET,
	mac_address MACADDR NOT NULL,
	first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	source VARCHAR(50)
);

-- Seed a few recent ARP rows observed in the live database (idempotent)
INSERT INTO mon.arp_table (node_id, ip_address, mac_address, first_seen, last_seen, source)
VALUES
	(1, '192.168.111.1',  'a8:f9:4b:ab:06:a0', now(), now(), 'arp'),
	(1, '192.168.111.8',  'f8:f0:82:10:55:d2', now(), now(), 'arp'),
	(1, '192.168.111.42', '00:08:7c:86:03:80', now(), now(), 'arp'),
	(1, '192.168.111.44', 'a4:56:30:9e:e3:c1', now(), now(), 'arp'),
	(1, '192.168.111.45', '00:15:f9:83:60:41', now(), now(), 'arp'),
	(1, '192.168.111.47', 'f8:f0:82:10:1b:0c', now(), now(), 'arp')
ON CONFLICT DO NOTHING;
