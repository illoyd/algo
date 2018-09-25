#!/usr/bin/env ruby

require 'workflow'
require 'csv'
#require 'datetime'

class Share
  include Comparable
  include Workflow
  workflow do
    state :new do
      event :open, transitions_to: :opened
    end
    state :opened do
      event :close, transitions_to: :closed
    end
    state :closed
  end

  attr_reader :asset, :open_price, :open_timestamp, :close_price, :close_timestamp

  def initialize(asset, open_price, open_timestamp)
    @asset = asset
    if open_price && open_timestamp
      open!(open_price, open_timestamp)
    end
  end

  def profit_or_loss
    if @close_price
      @close_price - @open_price
    else
      0.0
    end
  end

  def profit
    pl = self.profit_or_loss
    pl if pl > 0.0
  end

  def loss
    pl = self.profit_or_loss
    pl if pl < 0.0
  end

  def open_date
    @open_timestamp.strftime("%Y-%m-%d")
  end

  def open_time
    @open_timestamp.strftime("%H:%M:%S")
  end

  def close_date
    @close_timestamp&.strftime("%Y-%m-%d")
  end

  def close_time
    @close_timestamp&.strftime("%H:%M:%S")
  end

  def held_for
    if @close_timestamp
        @open_timestamp - @close_timestamp
    end


  def to_a
    [@asset, open_date, open_time, @open_price, close_date, close_time, @close_price, profit_or_loss, profit, loss]
  end

  def to_s
    "#{ @asset } #{ @open_timestamp }@#{ @open_price } #{ '/' if @close_timestamp } #{ @close_timestamp }#{ '@' if @close_timestamp }#{ @close_price }".strip
  end

  def <=>(other)
    to_a <=> other.to_a
  end

  protected

  def open(open_price, open_timestamp)
    @open_price = open_price
    @open_timestamp = open_timestamp
  end

  def close(close_price, close_timestamp)
    @close_price = close_price
    @close_timestamp = close_timestamp
  end

end

class FIFO
  extend Forwardable

  attr_reader :items

  def initialize()
    @items = []
  end

  def_delegator :items,  :shift

  def push(*args)
    @items.push(*args)
    @items.sort!
  end

end

class LotManager

  attr_reader :open_lots, :closed_lots

  def initialize
    @open_lots = Hash.new { |h,k| h[k] = FIFO.new }
    @closed_lots = Hash.new { |h,k| h[k] = FIFO.new }
  end

  def open(asset, open_price, open_timestamp, units)
    units = units.to_i
    open_price = open_price.to_f
    open_timestamp = DateTime.parse(open_timestamp)

    shares = units.times().to_a.map{ Share.new(asset, open_price, open_timestamp) }
    @open_lots[asset].push(*shares)
  end

  def close(asset, close_price, close_timestamp, units)
    units = units.to_i.abs
    close_price = close_price.to_f
    close_timestamp = DateTime.parse(close_timestamp)

    shares = @open_lots[asset].shift(units)
    shares.each { |share| share.close!(close_price, close_timestamp) }
    @closed_lots[asset].push(*shares)
  end
end

# If run from command line...

# Create the Lot Manager
lots = LotManager.new

# Open CSV
CSV.foreach("./orders.csv", headers: :first_row) do |order|

  # If line is a BUY, open shares
  case order['Trade Action'].upcase
  when 'BUY'
    puts "#{ order['Trade Action'] }: #{ order['Symbol'] } on #{ order['Trade Date'] } for #{ order['Price'] }@#{ order['Qty'] }"
    lots.open(order['Symbol'], order['Price'], order['Trade Date'], order['Qty'])
  when 'SELL'
    puts "#{ order['Trade Action'] }: #{ order['Symbol'] } on #{ order['Trade Date'] } for #{ order['Price'] }@#{ order['Qty'] }"
    lots.close(order['Symbol'], order['Price'], order['Trade Date'], order['Qty'])
  end

end

# Save shares to CSV
CSV.open("orders-analysis.csv", "wb") do |csv|
  csv << %w( asset open_date open_time open_price close_date close_time close_price profit_or_loss profit loss)

  # Output closed lots
  lots.closed_lots.each do |asset,lots|
    lots.items.each { |share| csv << share.to_a }
  end

  # Output open lots
  lots.open_lots.each do |asset,lots|
    lots.items.each { |share| csv << share.to_a }
  end
end
