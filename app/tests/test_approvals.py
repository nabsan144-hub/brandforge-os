def test_local_approval_link_lifecycle(client):
 r=client.post('/api/swarm/run',json={'campaign_name':'Approval flow','product_name':'Apex','industry':'Retail','target_audience':'Customers','key_benefits':'Clear price'})
 name=r.json()['campaign_name']; link=client.post(f'/api/campaigns/{name}/approval-links').json(); token=link['token']
 assert len(token)>30
 detail=client.get(f'/api/approvals/{token}'); assert detail.status_code==200
 portal=client.get(f'/approval/{token}'); assert portal.status_code==200 and 'CLIENT REVIEW' in portal.text
 updated=client.put(f'/api/approvals/{token}',json={'decision':'changes_requested','comment':'Please change the opening hook.'})
 assert updated.status_code==200 and updated.json()['approval']['comments'][0]['text'].startswith('Please')
 assert client.delete(f'/api/approvals/{token}').status_code==200
 assert client.get(f'/api/approvals/{token}').status_code==404
