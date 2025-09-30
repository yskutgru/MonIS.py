import requests
import json

# 1. Аутентификация
headers_auth = {
    'Authorization': 'DiadocAuth ddauth_api_client_id=api-5c190210-3c9b-407f-9802-3d897da607e9',
    'Content-Type': 'application/json'
}
params_auth = {'type': 'password'}
json_data_auth = {'login': 'Логин', 'password': 'Пароль'}

try:
    response_auth = requests.post(
        'https://diadoc-api.kontur.ru/V3/Authenticate',  # Исправлен URL
        params=params_auth, 
        headers=headers_auth,
        json=json_data_auth
    )
    response_auth.raise_for_status()  # Проверка на ошибки HTTP
    token_auth = response_auth.text.strip('"')  # Убираем кавычки если они есть
    print(f"Токен получен: {token_auth[:20]}...")
    
except requests.exceptions.RequestException as e:
    print(f"Ошибка аутентификации: {e}")
    exit(1)

# 2. Получение документов с пагинацией
url = "https://diadoc-api.kontur.ru/V3/GetDocuments"
params = {
    "boxId": "1b5b58eb-6fe9-4037-ae8d-c41156bf331b", 
    "filterCategory": "Any.Inbound"
}

headers = {
    'Authorization': f'DiadocAuth ddauth_api_client_id=api-5c190210-3c9b-407f-9802-3d897da607e9, ddauth_token={token_auth}',
    'Content-Type': 'application/json; charset=utf-8', 
    'Accept': 'application/json'
}

has_more_results = True
after_index_key = None
unique_entity_ids = set()
all_documents = []

try:
    while has_more_results:
        if after_index_key:
            params["afterIndexKey"] = after_index_key
            
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        has_more_results = data.get("HasMoreResults", False)
        documents = data.get("Documents", [])
        all_documents.extend(documents)
        
        # Собираем уникальные entity_id
        for document in documents:
            entity_id = document.get("EntityIdGuid")
            if entity_id:
                unique_entity_ids.add(entity_id)
        
        # Получаем ключ для следующей страницы
        if documents and has_more_results:
            after_index_key = documents[-1].get("IndexKey")
        else:
            after_index_key = None
            
        print(f"Получено документов: {len(documents)}. Всего: {len(all_documents)}")
        
    # Сохраняем все документы в файл
    with open('C:/test/test.json', 'w', encoding='utf-8') as f:
        json.dump({
            "total_documents": len(all_documents),
            "unique_entity_ids": list(unique_entity_ids),
            "documents": all_documents
        }, f, ensure_ascii=False, indent=4, sort_keys=True)
    
    print(f"Сохранено {len(all_documents)} документов в файл")
    print(f"Найдено уникальных entity_id: {len(unique_entity_ids)}")
    
except requests.exceptions.RequestException as e:
    print(f"Ошибка при получении документов: {e}")
except Exception as e:
    print(f"Неожиданная ошибка: {e}")