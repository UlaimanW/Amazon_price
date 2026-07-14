def chunk_products(products, columns=3):
    return [
        products[start:start + columns]
        for start in range(0, len(products), columns)
    ]
