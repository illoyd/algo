import sys
import csv
import json

import robinhood


##
# An order downloader
def download_orders_to_csv():
    # Create a new robinhood client
    client = robinhood.Client()

    # Download all orders
    print('Fetching orders')
    orders = client.orders.list()

    with open('orders.json', 'w', newline='') as file:
        data = [order.data for order in orders]
        file.writelines(data)

    return orders

    # Filter to only those orders with 'filled' state
    print('Keeping filled orders')
    orders = [order for order in orders if order['state'] == 'filled']

    # Sort
    print('Sorting orders')
    orders.sort(key=lambda order: order['last_transaction_at'])

    # Add symbol to each order
    print('Fetching symbols')
    for order in orders:
        order['symbol'] = client.instrument(order['instrument'])['symbol']
        print(order['symbol'])

    # Open the CSV and prepare a writer
    print('Writing to disk')
    with open('orders.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        # Write headers to CSV
        headers = (
            'Type', 'Trade Date', 'Settle Date', 'Symbol', 'Description', 'Trade Action', 'Qty', 'Price', 'Net Amount',
            'Instrument', 'Payload')
        writer.writerow(headers)

        # Write contents to CSV
        for order in orders:
            row = (
                'order',
                order['last_transaction_at'],
                None,
                order['symbol'],
                None,
                order['side'],
                order['cumulative_quantity'] or order['quantity'],
                order['average_price'] or order['price'],
                None,
                order['instrument'],
                order.data
            )
            print(row)
            writer.writerow(row)

    # Sign out
    client.logout()

##
# Run downloader?
