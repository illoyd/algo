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

  attr_reader :asset, :open_price, :open_time, :close_price, :close_time

  def initialize(asset, open_price, open_time)
    @asset = asset
    if open_price && open_time
      open!(open_price, open_time)
    end
  end

  def profit_or_loss
    if @close_price
      @close_price - @open_price
    else
      0.0
    end
  end

  def to_a
    [@asset, @open_time, @open_price, @close_time, @close_price]
  end

  def to_s
    "#{ @asset } #{ @open_time }@#{ @open_price } #{ '/' if @close_time } #{ @close_time }#{ '@' if @close_time }#{ @close_price }".strip
  end

  def <=>(other)
    to_a <=> other.to_a
  end

  protected

  def open(open_price, open_time)
    @open_price = open_price
    @open_time = open_time
  end

  def close(close_price, close_time)
    @close_price = close_price
    @close_time = close_time
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

  def open(asset, open_price, open_time, units)
    units = units.to_i
    open_price = open_price.to_f
    open_time = DateTime.parse(open_time)

    shares = units.times().to_a.map{ Share.new(asset, open_price, open_time) }
    @open_lots[asset].push(*shares)
  end

  def close(asset, close_price, close_time, units)
    units = units.to_i.abs
    close_price = close_price.to_f
    close_time = DateTime.parse(close_time)

    shares = @open_lots[asset].shift(units)
    shares.each { |share| share.close!(close_price, close_time) }
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
  csv << %w( asset open_time open_price close_time close_price )

  # Output closed lots
  lots.closed_lots.each do |asset,lots|
    lots.items.each { |share| csv << share.to_a }
  end

  # Output open lots
  lots.open_lots.each do |asset,lots|
    lots.items.each { |share| csv << share.to_a }
  end
end
