def test_campaign_revision_comparison(client):
 r=client.post('/api/swarm/run',json={'campaign_name':'Compare source','product_name':'Apex','industry':'Retail','target_audience':'Customers','key_benefits':'Clear price'}); name=r.json()['campaign_name']
 other=client.post(f'/api/campaigns/{name}/revisions').json()['name']
 response=client.get(f'/api/campaigns/{name}/compare/{other}')
 assert response.status_code==200
 data=response.json(); assert data['left']['name']==name and data['right']['name']==other and isinstance(data['copy_diff'],list)
