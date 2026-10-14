def predict(image,config,client,matcher=None):
    return client.chat(config['single_model'],image,'single',temperature=config['temperature'])
