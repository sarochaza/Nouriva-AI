"""Three sequential image-informed roles, with explicit dependencies and retained trace."""
def predict(image,config,client,matcher=None):
    models=config['multi_models'];kw={'temperature':config['temperature']}
    vision=client.chat(models[0],image,'vision',**kw)
    portion=client.chat(models[1],image,'portion',prior={'vision':vision},**kw)
    final=client.chat(models[2],image,'critic',prior={'vision':vision,'portion':portion},**kw)
    return {**final,'agent_trace':{'vision':vision,'portion':portion,'critic':final}}
